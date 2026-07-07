"""Generic pagination over provider result pages.

Providers describe *how to fetch one page*; :func:`paginate` drives the loop,
stopping when a page reports no more results, an optional page cap is hit, or the
requested ``max_results`` is reached. It is agnostic to page vs. cursor
addressing - the page number is passed to the fetch callable, which may map it
to an offset or a stored cursor.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Page[T]:
    """One page of results plus whether more pages exist."""

    items: tuple[T, ...] = ()
    has_more: bool = False
    #: Optional opaque cursor a provider may thread into its next request.
    next_cursor: str | None = field(default=None)


def paginate[T](
    fetch_page: Callable[[int], Page[T]],
    *,
    max_results: int,
    max_pages: int | None = None,
) -> list[T]:
    """Collect items across pages up to ``max_results``.

    :param fetch_page: Called with a 1-based page number; returns a :class:`Page`.
    :param max_results: Stop once this many items are collected (result is
        truncated to exactly this length).
    :param max_pages: Optional safety cap on the number of pages fetched.
    """
    if max_results <= 0:
        raise ValueError("max_results must be positive")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be positive when set")

    results: list[T] = []
    page_number = 1
    while len(results) < max_results:
        page = fetch_page(page_number)
        results.extend(page.items)
        if not page.has_more:
            break
        if max_pages is not None and page_number >= max_pages:
            break
        page_number += 1
    return results[:max_results]
