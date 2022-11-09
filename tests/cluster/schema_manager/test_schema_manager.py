import unittest

import pyspark.sql.types as T

from atc.configurator import Configurator
from atc.schema_manager import SchemaManager
from tests.cluster.schema_manager import extras


class TestSchemaManager(unittest.TestCase):
    def test_register_schema(self):
        manager = SchemaManager()

        schema = T.StructType(
            [
                T.StructField("Column1", T.IntegerType(), True),
                T.StructField("Column2", T.StringType(), True),
                T.StructField("Column3", T.FloatType(), True),
            ]
        )

        self.assertNotIn("register_test", manager._registered_schemas.keys())

        manager.register_schema(schema_name="register_test", schema=schema)

        self.assertIn("register_test", manager._registered_schemas.keys())

    def test_get_registered_schema(self):
        Configurator().add_resource_path(extras)
        manager = SchemaManager()

        schema = T.StructType(
            [
                T.StructField("Column1", T.IntegerType(), True),
                T.StructField("Column2", T.StringType(), True),
                T.StructField("Column3", T.FloatType(), True),
            ]
        )

        self.assertNotIn("register_test2", manager._registered_schemas.keys())

        manager.register_schema(schema_name="register_test2", schema=schema)

        self.assertEqual(
            manager.get_schema(schema_identifier="register_test2"),
            schema,
        )

    def test_get_python_ref_schema(self):
        Configurator().add_resource_path(extras)

        schema = SchemaManager().get_schema(schema_identifier="SchemaTestTable1")

        expected_schema = extras.python_test_schema

        self.assertEqual(schema, expected_schema)

    def test_get_sql_schema(self):
        Configurator().add_resource_path(extras)

        schema = SchemaManager().get_schema(schema_identifier="SchemaTestTable2")

        expected_schema = T.StructType(
            [
                T.StructField("a", T.IntegerType(), True),
                T.StructField("b", T.StringType(), True),
            ]
        )

        self.assertEqual(schema, expected_schema)

    # TODO #
    def test_get_json_schema(self):
        pass

    # TODO #
    def test_get_python_schema(self):
        pass

    def test_get_schema_as_string(self):
        Configurator().add_resource_path(extras)

        schema = SchemaManager().get_schema_as_string(
            schema_identifier="SchemaTestTable2"
        )

        self.assertEqual(schema, "a INTEGER, b STRING,")

    def test_get_all_schemas(self):
        Configurator().add_resource_path(extras)

        schemas_dict = SchemaManager().get_all_schemas()

        expected_schemas = {
            "python_test_schema": extras.python_test_schema,
            "SchemaTestTable1": extras.python_test_schema,
            "SchemaTestTable2": T.StructType(
                [
                    T.StructField("a", T.IntegerType(), True),
                    T.StructField("b", T.StringType(), True),
                ]
            ),
        }

        self.assertDictEqual(schemas_dict, expected_schemas)

    def test_get_all_spark_sql_schemas(self):
        Configurator().add_resource_path(extras)

        schemas_dict = SchemaManager().get_all_spark_sql_schemas()

        test_table_string = "a int, b int, c string, cplx struct<someId:string,details:struct<id:string>,blabla:array<int>>, d timestamp, m map<int,string>, p decimal(10,3), final string"
        expected_schemas = {
            "python_test_table": test_table_string,
            "SchemaTestTable1": test_table_string,
            "SchemaTestTable2": "a INTEGER, b STRING,",
        }

        self.assertDictEqual(schemas_dict, expected_schemas)


if __name__ == "__main__":
    unittest.main()
