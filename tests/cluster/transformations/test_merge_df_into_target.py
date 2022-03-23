import unittest

from atc.functions import get_unique_tempview_name
from atc.transformations import merge_df_into_target
from pyspark.sql.types import StructType, StructField, IntegerType, StringType
from atc.spark import Spark
from pyspark.sql import DataFrame
from atc.utils import DataframeCreator


class MergeDfIntoTargetTest(unittest.TestCase):
    db_name = "test" + get_unique_tempview_name()
    table_name = "testTarget"

    schema = StructType(
        [
            StructField("id", StringType(), False),
            StructField("sometext", StringType(), True),
            StructField("someinteger", IntegerType(), True),
        ]
    )

    cols = ["id", "sometext", "someinteger"]

    row1 = ("1", "text1", 25)
    row2 = ("2", "text2", 26)
    row3 = ("3", "text3", 27)
    data_rows = [
        row1,
        row2,
        row3,
    ]
    targetrow1 = ("ID1", "hello", 1)
    targetrow2 = ("1", "hello", 1)

    @classmethod
    def setUpClass(cls):
        cls.create_database(cls.db_name)
        cls.create_test_table(cls.table_name, cls.db_name)

    @classmethod
    def tearDownClass(cls) -> None:
        Spark.get().sql(f"drop database {cls.db_name} cascade")

    def test_01_insert(self):
        """Tests that a new row is inserted"""

        # Create target data
        Spark.get().sql(
            f"INSERT INTO {self.db_name}.{self.table_name} values {self.targetrow1}"
        )

        #  Merge dataframe into target
        df = self.create_data()
        merge_df_into_target(df, self.table_name, self.db_name, ["Id"])

        # Compare
        df_expected = self.expected_data_01()
        df_result = self.get_target_table()
        self.equal_dfs(df_expected, df_result)

    def test_02_merge(self):
        """Tests that a new row is merged"""

        # Truncate table
        Spark.get().sql(f"truncate table {self.db_name}.{self.table_name}")

        # Create target data
        Spark.get().sql(
            f"INSERT INTO {self.db_name}.{self.table_name} values {self.targetrow2}"
        )

        #  Merge dataframe into target
        df = self.create_data()
        merge_df_into_target(df, self.table_name, self.db_name, ["Id"])

        # Compare
        df_expected = self.expected_data_01()
        df_result = self.get_target_table()
        self.equal_dfs(df_expected, df_result)

    @classmethod
    def create_test_table(self, table_name="testTarget", db_name="test"):
        location = f"/tmp/{db_name}/{table_name}"
        sql_argument = f"""CREATE TABLE IF NOT EXISTS {db_name}.{table_name}(
                      Id STRING,
                      sometext STRING,
                      someinteger INT
                      )
                      USING DELTA
                      LOCATION '{location}'"""
        Spark.get().sql(sql_argument)

    @classmethod
    def create_database(self, db_name="test") -> None:
        location = f"/tmp/{db_name}/"
        sql_argument = f"CREATE DATABASE IF NOT EXISTS {db_name} LOCATION '{location}'"
        Spark.get().sql(sql_argument)

    def create_data(self) -> DataFrame:
        df_new = DataframeCreator.make_partial(
            schema=self.schema,
            columns=self.cols,
            data=self.data_rows,
        )

        return df_new.orderBy("id")

    def expected_data_01(self) -> DataFrame:
        df_new = DataframeCreator.make_partial(
            schema=self.schema,
            columns=self.cols,
            data=[self.targetrow1] + self.data_rows,
        )

        return df_new.orderBy("id")

    def expected_data_02(self) -> DataFrame:
        df_new = DataframeCreator.make_partial(
            schema=self.schema,
            columns=self.cols,
            data=[self.targetrow2, self.row2, self.row3],
        )

        return df_new.orderBy("id")

    def get_target_table(self):
        return Spark.get().read.table(f"{self.db_name}.{self.table_name}")

    def equal_dfs(self, df1, df2):
        df_expected_pd = df1.toPandas()
        df_result_pd = df2.toPandas()

        self.assertTrue(df_result_pd.equals(df_expected_pd))
