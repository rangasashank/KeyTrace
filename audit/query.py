import sys
import duckdb
from storage import table

# Read the current Iceberg snapshot, not a directory glob of stale Parquet files.
audit = table().scan().to_arrow()
db = duckdb.connect()
db.register("audit", audit)
sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT agent, action, decision, count(*) AS events FROM (SELECT DISTINCT * FROM audit) GROUP BY ALL ORDER BY agent, action, decision"
result = db.execute(sql)
print(" | ".join(column[0] for column in result.description))
for row in result.fetchall():
    print(" | ".join(str(value) for value in row))
