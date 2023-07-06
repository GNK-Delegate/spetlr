"""Simplified access to the databricks api."""

import json
import sys

from databricks.sdk import WorkspaceClient

from spetlr.functions import init_dbutils


def getDbApi() -> WorkspaceClient:
    """
    In local running, the databricks-sdk is used for configuration.
    Running on a cluster, the configuration is extracted from the job context.
    """
    try:
        dbutils = init_dbutils()
    except ModuleNotFoundError:
        # probably we are not in notebook
        dbutils = None

    if dbutils:
        context = json.loads(
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson()
        )
        host = context["extraContext"]["api_url"]
        token = context["extraContext"]["api_token"]
    else:
        try:
            cfg = WorkspaceClient().api_client

        except ModuleNotFoundError:
            print(
                "In local running, databricks-cli needs to be installed.",
                file=sys.stderr,
            )
            raise

        host = cfg.host
        token = cfg.token

    if not host or not token:
        raise Exception("Unable to auto-configure api client.")

    return WorkspaceClient(host=host, token=token)
