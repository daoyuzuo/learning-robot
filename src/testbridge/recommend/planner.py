"""Daily plan planner (temporary stub, replaced in Task 9)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DailyPlan:
    items: list = None


class Planner:
    def __init__(self, *args, **kwargs):
        pass

    def plan(self, now):
        return DailyPlan(items=[])
