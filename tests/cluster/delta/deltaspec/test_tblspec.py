import unittest

from spetlrtools.testing import DataframeTestCase

from spetlr import Configurator
from spetlr.deltaspec import TableSpecNotReadable
from spetlr.spark import Spark
from tests.cluster.delta.deltaspec import tables


@unittest.skipUnless(
    Spark.version() >= Spark.DATABRICKS_RUNTIME_11_3,
    "Drop column only supported from DBR 11.0",
)
class TestTableSpec(DataframeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        c = Configurator()
        c.clear_all_configurations()
        c.set_debug()

        c.register("mydb", dict(name="myDeltaTableSpecTestDb{ID}"))
        cls.base = tables.base
        cls.target = tables.target

        db = c.get("mydb", "name")
        Spark.get().sql(f"CREATE DATABASE {db};")

    @classmethod
    def tearDownClass(cls) -> None:
        c = Configurator()
        db = c.get("mydb", "name")
        # clean up after test.
        Spark.get().sql(f"DROP DATABASE {db} CASCADE")

    def test_tblspec(self):
        # at first the table does not exist
        diff = self.base.compare_to_name()
        self.assertTrue(diff.is_different(), diff)
        self.assertTrue(diff.nullbase(), diff)

        # then we make it exist
        self.base.make_storage_match()

        # now it exists and matches
        diff = self.base.compare_to_name()
        self.assertFalse(diff.is_different(), repr(diff))

        # but it does not match the target
        diff = self.target.compare_to_name()
        # the names are the same
        self.assertTrue(diff.name_match(), repr(diff))
        # the rest of the table is not the same
        self.assertTrue(diff.is_different(), repr(diff))

        # the table is not readable because of schema mismatch
        self.assertFalse(self.target.is_readable())

        # overwriting is possible and updates to the target schema
        df = Spark.get().createDataFrame([(1, "a", 3.14, "b", "c")], self.target.schema)
        self.target.make_storage_match(errors_as_warnings=True)

        self.target.get_dh().overwrite(df, overwriteSchema=True)

        # now the base no longer matches
        diff = self.base.compare_to_name()
        self.assertTrue(diff.is_different(), diff)

        # but the target matches.
        diff = self.target.compare_to_name()
        self.assertFalse(diff.is_different(), repr(diff))

    def test_name_change(self):
        spark = Spark.get()
        df = spark.createDataFrame([("eggs", 3.5, "spam")], tables.oldname.schema)
        tables.oldname.get_dh().overwrite(df)

        for stmt in tables.newname.compare_to(tables.oldname).alter_statements():
            spark.sql(stmt)

        diff = tables.newname.compare_to_name()
        self.assertTrue(diff.complete_match(), diff)
        self.assertEqual(tables.newname.read().count(), 1)

    def test_location_change(self):
        spark = Spark.get()
        df = spark.createDataFrame([("eggs", 3.5, "spam")], tables.oldlocation.schema)
        # we write the data to the old location
        tables.oldlocation.get_dh().overwrite(df)

        # location mismatch makes the tables not readable
        self.assertFalse(tables.newlocation.is_readable())

        # appending to the new table would fail, since it is not readable.
        with self.assertRaises(TableSpecNotReadable):
            tables.newlocation.append(df)

        # overwriting will update the table location.
        tables.newlocation.overwrite(df)

        diff = tables.newlocation.compare_to_name()
        self.assertTrue(diff.complete_match(), diff)
        self.assertEqual(tables.newlocation.read().count(), 1)
