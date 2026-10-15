from .base import JobSource
from .arbeitnow import ArbeitnowSource
from .greenhouse import GreenhouseSource
from .lever import LeverSource

__all__ = [
    "JobSource",
    "ArbeitnowSource",
    "GreenhouseSource",
    "LeverSource",
    "JobSpySource",
]


def __getattr__(name):
    # JobSpy is imported only when used, so the rest works without it.
    if name == "JobSpySource":
        from .jobspy_source import JobSpySource

        return JobSpySource

    raise AttributeError(name)