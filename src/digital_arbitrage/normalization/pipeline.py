"""The configurable normalization pipeline.

A pipeline is an ordered list of :class:`NormalizationStep` objects, each of
which mutates a :class:`NormalizedListing` in place. Steps are independent and
composable, so callers can add, remove, or reorder them to change behaviour
without touching the :class:`~digital_arbitrage.normalization.normalizer.Normalizer`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar

from .models import NormalizedListing


class NormalizationStep(ABC):
    """A single, named transformation applied to a NormalizedListing."""

    #: Unique, stable name used for pipeline management.
    name: ClassVar[str] = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a non-empty 'name'")

    @abstractmethod
    def apply(self, listing: NormalizedListing) -> None:
        """Mutate ``listing`` in place."""


class NormalizationPipeline:
    """An ordered, mutable collection of normalization steps."""

    def __init__(self, steps: Iterable[NormalizationStep] | None = None) -> None:
        self._steps: list[NormalizationStep] = list(steps or [])

    @property
    def steps(self) -> list[NormalizationStep]:
        """The steps, in execution order."""
        return list(self._steps)

    @property
    def step_names(self) -> list[str]:
        """The step names, in execution order."""
        return [step.name for step in self._steps]

    def add_step(self, step: NormalizationStep, *, index: int | None = None) -> None:
        """Insert ``step`` at ``index`` (append when ``index`` is None)."""
        if index is None:
            self._steps.append(step)
        else:
            self._steps.insert(index, step)

    def remove_step(self, name: str) -> None:
        """Remove the step with ``name`` (raises ``KeyError`` if absent)."""
        for i, step in enumerate(self._steps):
            if step.name == name:
                del self._steps[i]
                return
        raise KeyError(f"no step named {name!r}")

    def run(self, listing: NormalizedListing) -> NormalizedListing:
        """Apply every step to ``listing`` in order and return it."""
        for step in self._steps:
            step.apply(listing)
        return listing
