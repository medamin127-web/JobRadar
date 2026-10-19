from .base import JobSource
from .adzuna import AdzunaSource, adzuna_keys, adzuna_sources
from .arbeitnow import ArbeitnowSource
from .greenhouse import GreenhouseSource
from .jaabz import JaabzSource
from .lever import LeverSource
from .listed_boards import BOARDS, ListedBoard, country_board_sources
from .relocateme import RelocateMeSource
from .remote_boards import (
    HimalayasSource,
    RemoteOKSource,
    RemotiveSource,
    WeWorkRemotelySource,
    WorkingNomadsSource,
    remote_board_sources,
)
from .stepstone import StepStoneSource

__all__ = [
    "JobSource",
    "AdzunaSource",
    "adzuna_keys",
    "adzuna_sources",
    "ArbeitnowSource",
    "BOARDS",
    "ListedBoard",
    "country_board_sources",
    "GreenhouseSource",
    "JaabzSource",
    "LeverSource",
    "RelocateMeSource",
    "HimalayasSource",
    "RemoteOKSource",
    "RemotiveSource",
    "WeWorkRemotelySource",
    "WorkingNomadsSource",
    "remote_board_sources",
    "StepStoneSource",
    "JobSpySource",
]


def __getattr__(name):
    # JobSpy is imported only when used, so the rest works without it.
    if name == "JobSpySource":
        from .jobspy_source import JobSpySource

        return JobSpySource

    raise AttributeError(name)