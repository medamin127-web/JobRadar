from dataclasses import dataclass
from typing import Optional


@dataclass
class Language:
    """
    Represents a language in the candidate profile.
    """

    name: str

    level: Optional[str] = None

    certification: Optional[str] = None

    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "certification": self.certification,
        }