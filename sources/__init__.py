from .base import JobSource
from .arbeitnow import ArbeitnowSource
from .greenhouse import GreenhouseSource
from .jaabz import JaabzSource
from .lever import LeverSource
from .relocateme import RelocateMeSource
from .stepstone import StepStoneSource

__all__ = [
    "JobSource",
    "ArbeitnowSource",
    "GreenhouseSource",
    "JaabzSource",
    "LeverSource",
    "RelocateMeSource",
    "StepStoneSource",
    "JobSpySource",
]


def __getattr__(name):
    # JobSpy is imported only when used, so the rest works without it.
    if name == "JobSpySource":
        from .jobspy_source import JobSpySource

        return JobSpySource

    raise AttributeError(name)