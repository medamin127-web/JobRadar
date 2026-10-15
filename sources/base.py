from abc import ABC, abstractmethod
import pandas as pd


class JobSource(ABC):

    @abstractmethod
    def search(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        hours_old: int,
        country: str = None,
    ) -> pd.DataFrame:
        """
        Search for jobs and return them as a pandas DataFrame.
        """
        pass