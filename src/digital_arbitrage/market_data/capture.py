"""Transport-level request/response capture for the collector.

:class:`RecordingTransport` wraps the provider's *API* transport (never the
OAuth token transport) so every exchange - search pages, detail calls, error
bodies, retries - is observed without changing provider parsing. Request
headers are never seen by the sink; only the redacted method+URL and the
sanitised response body are persisted.

:class:`RequestBudget` enforces a shared per-provider daily request budget.
Because the check happens at transport level, retries and enrichment calls
count exactly like first-attempt requests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..providers.live.errors import ProviderError
from ..providers.live.http import HttpRequest, HttpResponse, Transport
from .redaction import redact_payload, redact_request


class BudgetExhaustedError(Exception):
    """Raised by :class:`RequestBudget` when a provider's daily budget is spent."""

    def __init__(self, provider: str, day: str, limit: int) -> None:
        super().__init__(f"[{provider}] daily request budget exhausted for {day} (limit {limit})")
        self.provider = provider
        self.day = day
        self.limit = limit


class RequestBudget:
    """Shared per-provider daily request cap.

    ``usage(provider)`` is supplied by the caller (backed by the
    ``request_usage`` table) so retries, enrichment calls and earlier runs on
    the same UTC day all count against the same budget.
    """

    def __init__(
        self,
        limits: dict[str, int],
        usage: Callable[[str], int],
        *,
        day: str | None = None,
    ) -> None:
        self._limits = dict(limits)
        self._usage = usage
        self._day = day or datetime.now(UTC).date().isoformat()
        self._local: dict[str, int] = {}

    @property
    def day(self) -> str:
        return self._day

    def check(self, provider: str) -> None:
        """Raise :class:`BudgetExhaustedError` if ``provider`` is over budget."""
        limit = self._limits.get(provider)
        if limit is None:
            return
        used = self._usage(provider) + self._local.get(provider, 0)
        if used >= limit:
            raise BudgetExhaustedError(provider, self._day, limit)

    def record(self, provider: str) -> None:
        """Note that ``provider`` consumed one request of today's budget."""
        self._local[provider] = self._local.get(provider, 0) + 1

    def consumed(self, provider: str) -> int:
        """Requests recorded through this budget object this process."""
        return self._local.get(provider, 0)


class PayloadSink:
    """Persisted-exchange sink driven by :class:`RecordingTransport`.

    The collector calls :meth:`begin_task` before sending a page/detail
    request so captured payloads are linked to their task. A ``None`` task
    context captures anyway (payload kept, unlinked) - captured data is never
    silently dropped.
    """

    def __init__(
        self,
        store: Any,  # MarketDataStore - duck-typed to avoid an import cycle
        run_id: str,
        provider: str,
        endpoint_resolver: Callable[[str], str],
        *,
        keep_seller_usernames: bool = False,
        budget: RequestBudget | None = None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._provider = provider
        self._endpoint_resolver = endpoint_resolver
        self._keep_sellers = keep_seller_usernames
        self._budget = budget
        self._task_id: int | None = None
        self._attempts = 0

    def begin_task(self, task_id: int | None) -> None:
        self._task_id = task_id
        self._attempts = 0

    @property
    def attempts(self) -> int:
        """Sends observed since :meth:`begin_task` (1 + retries)."""
        return self._attempts

    def __call__(
        self,
        request: HttpRequest,
        response: HttpResponse | None,
        error: BaseException | None,
    ) -> None:
        self._attempts += 1
        provider = self._provider
        self._store.record_request(
            day=self._budget.day if self._budget else datetime.now(UTC).date().isoformat(),
            provider=provider,
        )
        if self._budget is not None:
            self._budget.record(provider)
        if response is None or not response.body:
            return
        safe_request = redact_request(request)
        body = redact_payload(
            response.body, provider=provider, keep_seller_usernames=self._keep_sellers
        )
        self._store.record_payload(
            collection_run_id=self._run_id,
            task_id=self._task_id,
            endpoint=self._endpoint_resolver(request.url),
            request_url=safe_request["url"],
            http_status=response.status,
            payload_json=body,
            payload_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )


class RecordingTransport(Transport):
    """A :class:`Transport` that forwards to ``inner`` and reports each send.

    ``budget`` is checked *before* every send so exhausted budgets fail fast at
    transport level; the error is deliberately not a ``ProviderError`` subclass
    so the retry runner never retries budget exhaustion.
    """

    def __init__(
        self,
        inner: Transport,
        sink: Callable[[HttpRequest, HttpResponse | None, BaseException | None], None],
        *,
        provider: str | None = None,
        budget: RequestBudget | None = None,
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._provider = provider
        self._budget = budget

    def send(self, request: HttpRequest) -> HttpResponse:
        if self._budget is not None and self._provider is not None:
            self._budget.check(self._provider)
        try:
            response = self._inner.send(request)
        except ProviderError as err:
            self._report(request, None, err)
            raise
        self._report(request, response, None)
        return response

    def _report(
        self,
        request: HttpRequest,
        response: HttpResponse | None,
        error: BaseException | None,
    ) -> None:
        try:
            self._sink(request, response, error)
        except Exception:  # noqa: BLE001 - capture must never break collection
            pass
