"""Readiness scoring (temporary stub, replaced in Task 8)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessView:
    total: float = 0.0


def calculate_readiness(pack, goal, mastery):
    return ReadinessView()
