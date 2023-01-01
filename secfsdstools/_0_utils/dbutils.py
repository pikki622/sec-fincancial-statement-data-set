"""
Basic DB handling functionality
"""

import logging
import os
import sqlite3
from abc import ABC
from dataclasses import Field
from typing import List, TypeVar, Tuple

import pandas as pd

T = TypeVar("T")  # pylint: disable=W0621

LOGGER = logging.getLogger(__name__)


# noinspection SqlResolve
class DB(ABC):
    """
    Base class for DB handling. Provides some basic functionality.
    """

    def __init__(self, db_dir="db/"):
        self.db_dir = db_dir
        self.database = os.path.join(self.db_dir, 'secfsdstools.db')

    def get_connection(self) -> sqlite3.Connection:
        """
        creates a connection to the db.
        :return: sqlite3 connection instance
        """
        return sqlite3.connect(self.database)

    def execute_read_as_df(self, sql: str) -> pd.DataFrame:
        """
        directly read the content into a pandas dataframe
        :param sql: Select String
        :return: pd.DataFrame
        """
        conn = self.get_connection()
        try:
            LOGGER.debug("execute %s", sql)
            return pd.read_sql_query(sql, conn)
        finally:
            conn.close()

    def execute_single(self, sql: str):
        """
        executes a single sql statement without any parameters.
        :param sql: sql string, not paramterized
        """
        conn = self.get_connection()
        try:
            LOGGER.debug("execute %s", sql)
            conn.execute(sql)
            conn.commit()
        finally:
            conn.close()

    def execute_many(self, sql: str, params: List[Tuple]):
        """
        executes a parameterized statement for every tuple in the params list
        :param sql: parameterized statement
        :param params: list with tuples containing the parameters
        """
        conn = self.get_connection()
        try:
            LOGGER.debug("execute %s", sql)
            conn.executemany(sql, params)
            conn.commit()
        finally:
            conn.close()

    def execute_fetchall(self, sql: str) -> List[Tuple]:
        """
        returns all results of the sql
        :param sql: sql statement
        :return: list with tuples
        """
        conn = self.get_connection()
        try:
            LOGGER.debug("execute %s", sql)
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def execute_fetchall_typed(self, sql: str, T) -> List[T]:  # pylint: disable=W0621,C0103
        """fetches all data of the sql statement and directly wraps it
        into the provided type.
        Note all selected columns in the sql have to exist with the same
         name in the dataclass of type T.

        :param sql: sql string
        :param T: type class
        :return: list of instances of the type
        """
        conn = self.get_connection()
        try:
            LOGGER.debug("execute %s", sql)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            results = cursor.fetchall()
            return [T(**dict(x)) for x in results]
        finally:
            conn.close()

    def create_insert_statement_for_dataclass(self, table_name: str, data):
        """
        creates the insert sql statement based on the fields of a dataclass

        :param table_name: name of the table to insert into
        :param data: object of the dataclass
        :return: 'insert into' statement
        """
        # todo: None handling
        fields: List[Field]
        if isinstance(data.__dataclass_fields__, dict):
            # __dataclass_fields__ is a dict, so you can use the
            # .values() method to get the Field objects
            fields = data.__dataclass_fields__.values()
        else:  # from python 3.10
            # __dataclass_fields__ is a tuple, so you can just use it directly
            fields = data.__dataclass_fields__

        column_list = [f"'{field.name}'" for field in fields]
        value_list = []
        for field in fields:
            quotes = ""
            if field.type == str:
                quotes = "'"
            value_list.append(quotes + str(getattr(data, field.name)) + quotes)

        column_str = ', '.join(column_list)
        value_str = ', '.join(value_list)
        return f"INSERT INTO {table_name} ({column_str}) VALUES ({value_str})"
