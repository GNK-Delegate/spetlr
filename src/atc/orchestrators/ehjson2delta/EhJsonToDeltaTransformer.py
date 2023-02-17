from pyspark.sql import DataFrame
from pyspark.sql import functions as f

from atc.delta import DeltaHandle
from atc.eh import EventHubCaptureExtractor
from atc.etl import Transformer


class EhJsonToDeltaTransformer(Transformer):
    def __init__(
        self,
        eh: EventHubCaptureExtractor,
        target_dh: DeltaHandle,
        keep_body_as_json: bool = False,
    ):
        super().__init__()
        self.eh = eh
        self.target_dh = target_dh

        # If true, the body is saved as a column called "BodyJson"
        self._keep_body_as_json = keep_body_as_json

    def process(self, df: DataFrame) -> DataFrame:
        # use the schema from the target table to decide what to unpack
        target_df = self.target_dh.read()
        source_df = df

        # these columns will be copied directly from the source data frame
        direct_cols = [col for col in target_df.columns if col in source_df.columns]
        # verify that the schema of direct columns matches
        for col in direct_cols:
            target_type = target_df.select(col).schema.fields[0].dataType
            source_type = source_df.select(col).schema.fields[0].dataType
            if target_type != source_type:
                raise TypeError(
                    "The target table has incorrect type for "
                    f"direct column {col}, "
                    f"expected {source_type}, got {target_type}."
                )

        # The body is saved as string format as "BodyJson"
        if self._keep_body_as_json:
            df = df.withColumn("BodyJson", f.col("Body").cast("string"))

        if "Body" in direct_cols:
            if self._keep_body_as_json:
                df = df.select(*direct_cols, "BodyJson")
            else:
                df = df.select(*direct_cols)
        else:
            # every column that is in the target delta table and that is not a direct
            # column from the source eventhub DataFrame, is assumed to be a column whose
            # value can be unpacked from the json that is in the eventhub body
            body_cols = [
                col for col in target_df.columns if col not in source_df.columns
            ]
            body_schema = target_df.select(*body_cols).schema
            df = df.withColumn(
                "Body",
                f.from_json(f.decode("Body", "utf-8"), body_schema).alias("Body"),
            )
            if self._keep_body_as_json:
                df = df.select("Body.*", *direct_cols, "BodyJson")
            else:
                df = df.select("Body.*", *direct_cols)

        return df
