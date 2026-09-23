import os
from pathlib import Path
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType

FIELDS = ["event_id", "timestamp", "agent", "action", "decision", "reason"]

def table():
    root = Path(os.getenv("WAREHOUSE", "/data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog("keytrace", type="sql", uri=f"sqlite:///{root}/catalog.db", warehouse=f"file://{root}/warehouse")
    catalog.create_namespace_if_not_exists("security")
    return catalog.create_table_if_not_exists("security.audit", schema=Schema(*[
        NestedField(i, name, StringType(), required=False) for i, name in enumerate(FIELDS, 1)
    ]))

def append(target, events):
    target.append(pa.Table.from_pylist(events, schema=pa.schema([(name, pa.string()) for name in FIELDS])))
