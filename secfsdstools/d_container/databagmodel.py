"""
Defines the container that keeps the data of sub.txt, num.txt, and  pre.txt together.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, TypeVar

import pandas as pd

from secfsdstools.a_utils.constants import SUB_TXT, PRE_TXT, NUM_TXT, PRE_NUM_TXT
from secfsdstools.d_container.filter import FilterBase

RAW = TypeVar('RAW', bound='RawDataBag')
JOINED = TypeVar('JOINED', bound='JoinedDataBag')


class JoinedDataBag:

    @classmethod
    def create(cls, sub_df: pd.DataFrame, pre_num_df: pd.DataFrame) -> JOINED:
        return JoinedDataBag(sub_df=sub_df, pre_num_df=pre_num_df)

    def __init__(self, sub_df: pd.DataFrame, pre_num_df: pd.DataFrame):
        self.sub_df = sub_df
        self.pre_num_df = pre_num_df

    def get_sub_copy(self) -> pd.DataFrame:
        """
        Returns a copy of the sub dataframe.

        Returns:
            pd.DataFrame: copy of the sub dataframe.
        """
        return self.sub_df.copy()

    def get_pre_num_copy(self) -> pd.DataFrame:
        """
        Returns a copy of the joined pre_num dataframe.

        Returns:
            pd.DataFrame: copy of joined pre_num dataframe.
        """
        return self.pre_num_df.copy()

    def save(self, target_path: str):
        """
        Stores the bag under the given directory.
        The directory has to exist and must be empty.

        Args:
            databag: the bag to be saved
            target_path: the directory under which the parquet files for sub and pre_num
                  will be created

        """
        if not os.path.isdir(target_path):
            raise ValueError(f"the path {target_path} does not exist")

        if len(os.listdir(target_path)) > 0:
            raise ValueError(f"the target_path {target_path} is not empty")

        self.sub_df.to_parquet(os.path.join(target_path, f'{SUB_TXT}.parquet'))
        self.pre_num_df.to_parquet(os.path.join(target_path, f'{PRE_NUM_TXT}.parquet'))

    @staticmethod
    def load(target_path: str) -> JOINED:
        """
        Loads the content of the current bag at the specified location.

        Args:
            target_path: the directory which contains the parquet files for sub and pre_num

        Returns:
            JoinedDataBag: the loaded Databag
        """
        sub_df = pd.read_parquet(os.path.join(target_path, f'{SUB_TXT}.parquet'))
        pre_num_df = pd.read_parquet(os.path.join(target_path, f'{PRE_NUM_TXT}.parquet'))

        return JoinedDataBag.create(sub_df=sub_df, pre_num_df=pre_num_df)

    @staticmethod
    def concat(bags: List[JOINED]) -> JOINED:
        """
        Merges multiple Bags together into one bag.
        Note: merge does not check if DataBags with the same reports are merged together.

        Args:
            bags: List of bags to be merged

        Returns:
            JoinedDataBag: a Bag with the merged content

        """
        sub_dfs = [db.sub_df for db in bags]
        pre_num_dfs = [db.pre_num_df for db in bags]

        return JoinedDataBag.create(sub_df=pd.concat(sub_dfs),
                                    pre_num_df=pd.concat(pre_num_dfs))


@dataclass
class RawDataBagStats:
    """
    Contains simple statistics of a report.
    """
    num_entries: int
    pre_entries: int
    number_of_reports: int
    reports_per_form: Dict[str, int]
    reports_per_period_date: Dict[int, int]


class RawDataBag:
    """
    Container class to keep the data for sub.txt, pre.txt, and num.txt together.
    """

    @classmethod
    def create(cls, sub_df: pd.DataFrame, pre_df: pd.DataFrame, num_df: pd.DataFrame) -> RAW:
        return RawDataBag(sub_df=sub_df, pre_df=pre_df, num_df=num_df)

    def __init__(self, sub_df: pd.DataFrame, pre_df: pd.DataFrame, num_df: pd.DataFrame):
        self.sub_df = sub_df
        self.pre_df = pre_df
        self.num_df = num_df

        # pandas pivot works better if coreg is not nan, so we set it here to a simple dash
        self.num_df.loc[self.num_df.coreg.isna(), 'coreg'] = '-'

    def __getitem__(self, filter):
        return self.filter(filter)

    def filter(self, filter: FilterBase[RAW]) -> RAW:
        return filter.filter(self)

    def get_sub_copy(self) -> pd.DataFrame:
        """
        Returns a copy of the sub.txt dataframe.

        Returns:
            pd.DataFrame: copy of the sub.txt dataframe.
        """
        return self.sub_df.copy()

    def get_pre_copy(self) -> pd.DataFrame:
        """
        Returns a copy of the pre.txt dataframe.

        Returns:
            pd.DataFrame: copy of the pre.txt dataframe.
        """
        return self.pre_df.copy()

    def get_num_copy(self) -> pd.DataFrame:
        """
        Returns a copy of the num.txt dataframe.

        Returns:
            pd.DataFrame: copy of the num.txt dataframe.
        """
        return self.num_df.copy()

    def get_joined_bag(self) -> JoinedDataBag:
        """
        merges the raw data of pre and num together.

        Returns:
            JoinedDataBag: the DataBag where pre and num are merged

        """

        # merge num and pre together. only rows in num are considered for which entries in pre exist
        pre_num_df = pd.merge(self.num_df,
                              self.pre_df,
                              on=['adsh', 'tag',
                                  'version'])  # don't produce index_x and index_y columns

        return JoinedDataBag.create(sub_df=self.sub_df, pre_num_df=pre_num_df)

    def statistics(self) -> RawDataBagStats:
        """
        calculate a few simple statistics of a report.
        - number of entries in the num-file
        - number of entries in the pre-file
        - number of reports in the zip-file (equals number of entries in sub-file)
        - number of reports per form (10-K, 10-Q, ...)
        - number of reports per period date (counts per value in the period column of sub-file)

        Returns:
            RawDataBagStats: instance with basic report infos
        """

        num_entries = len(self.num_df)
        pre_entries = len(self.pre_df)
        number_of_reports = len(self.sub_df)
        reports_per_period_date: Dict[int, int] = self.sub_df.period.value_counts().to_dict()
        reports_per_form: Dict[str, int] = self.sub_df.form.value_counts().to_dict()

        return RawDataBagStats(num_entries=num_entries,
                               pre_entries=pre_entries,
                               number_of_reports=number_of_reports,
                               reports_per_form=reports_per_form,
                               reports_per_period_date=reports_per_period_date
                               )

    def save(self, target_path: str):
        """
        Stores the bag under the given directory.
        The directory has to exist and must be empty.

        Args:
            databag: the bag to be saved
            target_path: the directory under which three parquet files for sub_txt, pre_text,
                  and num_txt will be created

        """
        if not os.path.isdir(target_path):
            raise ValueError(f"the path {target_path} does not exist")

        if len(os.listdir(target_path)) > 0:
            raise ValueError(f"the target_path {target_path} is not empty")

        self.sub_df.to_parquet(os.path.join(target_path, f'{SUB_TXT}.parquet'))
        self.pre_df.to_parquet(os.path.join(target_path, f'{PRE_TXT}.parquet'))
        self.num_df.to_parquet(os.path.join(target_path, f'{NUM_TXT}.parquet'))

    @staticmethod
    def load(target_path: str) -> RAW:
        """
        Loads the content of the current bag at the specified location.

        Args:
            target_path: the directory which contains the three parquet files for sub_txt, pre_txt,
             and num_txt

        Returns:
            RawDataBag: the loaded Databag
        """
        sub_df = pd.read_parquet(os.path.join(target_path, f'{SUB_TXT}.parquet'))
        pre_df = pd.read_parquet(os.path.join(target_path, f'{PRE_TXT}.parquet'))
        num_df = pd.read_parquet(os.path.join(target_path, f'{NUM_TXT}.parquet'))

        return RawDataBag.create(sub_df=sub_df, pre_df=pre_df, num_df=num_df)

    @staticmethod
    def concat(bags: List[RAW]) -> RAW:
        """
        Merges multiple Bags together into one bag.
        Note: merge does not check if DataBags with the same reports are merged together.

        Args:
            bags: List of bags to be merged

        Returns:
            RawDataBag: a Bag with the merged content

        """
        sub_dfs = [db.sub_df for db in bags]
        pre_dfs = [db.pre_df for db in bags]
        num_dfs = [db.num_df for db in bags]

        # todo: might be more efficient if the contained maps were just combined
        #       instead of being recalculated
        return RawDataBag.create(sub_df=pd.concat(sub_dfs),
                                 pre_df=pd.concat(pre_dfs),
                                 num_df=pd.concat(num_dfs))
