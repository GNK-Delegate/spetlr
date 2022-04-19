import unittest

from pyspark.sql.utils import AnalysisException

from atc.config_master import TableConfigurator
from atc.delta import DeltaHandle
from atc.delta.db_handle import DbHandle
from atc.spark import Spark


class DeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TableConfigurator().clear_all_configurations()

    def test_01_configure(self):
        tc = TableConfigurator()
        tc.register(
            "MyDb", {"name": "TestDb{ID}", "location": "/mnt/atc/silver/testdb{ID}"}
        )

        tc.register(
            "MyTbl",
            {
                "name": "TestDb{ID}.TestTbl",
                "location": "/mnt/atc/silver/testdb{ID}/testtbl",
            },
        )

        # test instantiation without error
        DbHandle.from_tc("MyDb")
        DeltaHandle.from_tc("MyTbl")

    def test_02_create(self):
        db = DbHandle.from_tc("MyDb")
        db.create()

        dh = DeltaHandle.from_tc("MyTbl")
        dh.create_hive_table()

    def test_03_write(self):
        dh = DeltaHandle.from_tc("MyTbl")

        df = Spark.get().createDataFrame([(1, "a"), (2, "b")], "id int, name string")

        dh.overwrite(df)
        dh.append(df)

    def test_04_read(self):
        df = DeltaHandle.from_tc("MyTbl").read()
        self.assertEqual(4, df.count())

    def test_05_truncate(self):
        dh = DeltaHandle.from_tc("MyTbl")
        dh.truncate()
        df = dh.read()
        self.assertEqual(0, df.count())

    def test_06_delete(self):
        dh = DeltaHandle.from_tc("MyTbl")
        dh.drop_and_delete()

        with self.assertRaises(AnalysisException):
            dh.read()
