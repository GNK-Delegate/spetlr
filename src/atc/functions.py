"""
A collection of useful pyspark snippets.
"""

from atc.spark import Spark
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType
import uuid as _uuid

# Pyspark uuid function implemented as recommended here
# https://stackoverflow.com/questions/49785108/spark-streaming-with-python-how-to-add-a-uuid-column/50095755
uuid = udf(lambda: str(_uuid.uuid4()), StringType()).asNondeterministic()  # noqa

def init_dbutils():
    try:
        from pyspark.dbutils import DBUtils
        dbutils = DBUtils(Spark.get())
    except ImportError:
        import IPython
        dbutils = IPython.get_ipython().user_ns["dbutils"]
    return dbutils

class NoTableException(Exception):
    pass


def drop_table_cascade(DBDotTableName: str ) -> None:
    """
    drop_table_cascade drops a databricks database table and remove the files permanently

    :param p1: db.tablename

    return None
    
    """

    #Check if table exists 
    if Spark.get()._jsparkSession.catalog().tableExists(DBDotTableName):

        # Get table path 
        table_path=str(Spark.get().sql(f"DESCRIBE DETAIL {DBDotTableName}").collect()[0]["location"])
        
        if table_path is None:
            raise NoTableException(f"Table path is NONE.")
        
        # Remove table 
        Spark.get().sql(f"DROP TABLE IF EXISTS {DBDotTableName}")
        # Remove files associated with table        
        init_dbutils().fs.rm(table_path, recurse=True) 

    else:
        raise NoTableException(f"The table {DBDotTableName} not found. Rembember syntax db.tablename.")