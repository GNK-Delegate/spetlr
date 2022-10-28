from datetime import datetime as dt
from datetime import timezone
from typing import Optional

from pyspark.sql import DataFrame
from pyspark.sql import functions as f

from atc.delta import DeltaHandle
from atc.eh.EventHubCaptureExtractor import EventHubCaptureExtractor
from atc.etl import Extractor
from atc.orchestrators.ehjson2delta import EhJsonToDeltaException
from atc.spark import Spark


class EhJsonToDeltaExtractor(Extractor):
    """
    This extractor has a side effect on the delta table!

    Get the highest previously read partition from the delta table.
    Truncate all rows from the delta table that come from that partition.
    Extract all rows from the EventHubCaptureExtractor from that partition on.
    """

    def __init__(
        self, eh: EventHubCaptureExtractor, dh: DeltaHandle, dataset_key: str = None
    ):
        super().__init__(dataset_key=dataset_key)
        self.eh = eh
        self.dh = dh

    def _read_pdate_partitioned(self) -> DataFrame:
        """get the highest pdate partition,
        truncate it,
        read the event hub from that partition"""
        max_pdate: Optional[dt] = (
            self.dh.read().groupBy().agg(f.max("pdate")).collect()[0][0]
        )
        if max_pdate is None:
            # if it is None, no previous data exists,
            # so don't truncate and read everything
            return self.eh.read()

        max_pdate = max_pdate.astimezone(timezone.utc)

        # truncate this largest partition...
        Spark.get().sql(
            f"TRUNCATE TABLE {self.dh.get_tablename()} "
            f" PARTITION (pdate='{max_pdate.isoformat()}')"
        )
        # the datetime literal specification:
        # https://spark.apache.org/docs/latest/sql-ref-literals.html#datetime-literal
        # ...it works with the python datetime .isoformat()

        # ...and read it back from eventhub
        return self.eh.read(from_partition=max_pdate)

    def _read_ymd_ymdh_partitioned(self) -> DataFrame:
        """get the highest partition, piece by piece,
        truncate it,
        construct the datetime that the pieces correspond to,
        read the event hub from that datetime"""

        dh_parts = self.dh.get_partitioning()

        # this df will be filtered stepwise
        df = self.dh.read()

        y = df.groupBy().agg(f.max("y")).collect()[0][0]
        if y is None:
            # if it is None, no previous data exists,
            # so don't truncate and read everything
            return self.eh.read()

        # continue the logic. We know there is a partition.
        truncate_partiton_spec = f"y={y}"
        df = df.filter(f"y={y}")

        # if there was a y, there is a partition and hence the others must exist
        m = df.groupBy().agg(f.max("m")).collect()[0][0]
        truncate_partiton_spec += f",m={m}"
        df = df.filter(f"m={m}")

        d = df.groupBy().agg(f.max("d")).collect()[0][0]
        truncate_partiton_spec += f",d={d}"
        df = df.filter(f"d={d}")

        if "h" in dh_parts:
            h = df.groupBy().agg(f.max("h")).collect()[0][0]
            truncate_partiton_spec += f",h={h}"
        else:
            h = 0

        Spark.get().sql(
            f"TRUNCATE TABLE {self.dh.get_tablename()} "
            f" PARTITION ({truncate_partiton_spec})"
        )

        read_from = dt(y, m, d, h, tzinfo=timezone.utc)

        return self.eh.read(from_partition=read_from)

    def read(self) -> DataFrame:

        # we need to find out 2 things,
        # - what (if any) to truncate from the delta table,
        # - and where to read the eventhub from (or ead everything)

        # first check if the partitioning is usable
        eh_parts = self.eh.get_partitioning()
        dh_parts = self.dh.get_partitioning()

        if dh_parts == ["pdate"]:
            return self._read_pdate_partitioned()
        if dh_parts == eh_parts:
            # its ymd or ymdh
            return self._read_ymd_ymdh_partitioned()
        else:
            raise EhJsonToDeltaException("Delta table has bad partitioning")
