from typing import List, Union

import pycountry
import pyspark.sql.functions as F
import pyspark.sql.types as T
from pyspark.sql import DataFrame

from spetlr.etl import TransformerNC


def translate_country_to_alpha2(country_name: str) -> str:
    """Translate a simple country name into an alpha-2 code"""
    return pycountry.countries.get(name=country_name).alpha_2


translateUDF = F.udf(lambda z: translate_country_to_alpha2(z), T.StringType())


class CountryToAlphaCodeTransformerNC(TransformerNC):
    def __init__(
        self,
        col_name: str,
        output_col_name: str = None,
        dataset_input_keys: Union[str, List[str]] = None,
        dataset_output_key: str = None,
    ) -> None:
        """
        A simple transformer to translate country names to alpha-2 codes

        Args:
            col_name: The name of the column with country names
            output_col_name: The name of the column to create,
            defaults to col_name if none is given
        """
        super().__init__(
            dataset_input_keys=dataset_input_keys,
            dataset_output_key=dataset_output_key,
        )
        self.col_name = col_name
        self.output_col_name = output_col_name or self.col_name

    def process(self, df: DataFrame) -> DataFrame:
        """
        Method to add column to passed dataframe 'df'
        Args:
            df: The dataframe to work on
        Returns:
            The dataframe with an added or overwritten column
        """
        df = df.withColumn(self.output_col_name, translateUDF(F.col(self.col_name)))
        return df
