# ingest_instagram_posts.py  ✅ MERGE-fixed
import json
import duckdb
import pandas as pd

JSON_PATH = r"C:\Users\hafss\OneDrive\Desktop\Final\multi-agent-system-for-identity-revelalion-and-reporting\notebooks\databases\instagram\instagram_posts_balaouane_hassan.json"
DB_PATH   = r"C:\Users\hafss\OneDrive\Desktop\Final\multi-agent-system-for-identity-revelalion-and-reporting\notebooks\databases\instagram\instagram_data.duckdb"

# --- Load JSON -> DataFrame
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.json_normalize(data)

# Ensure columns the rest of your pipeline expects
if "isPinned" not in df.columns:
    df["isPinned"] = False

# Normalize types that can drift
df["id"] = df["id"].astype(str)

# --- Open DB
con = duckdb.connect(DB_PATH)
con.register("df_new", df)

# Create table if missing from the current DF schema
con.execute("""
CREATE TABLE IF NOT EXISTS posts AS
SELECT * FROM df_new LIMIT 0
""")

# Add any new columns that appeared in the JSON since last run (schema drift safe)
existing_cols = [row[1] for row in con.execute("PRAGMA table_info('posts')").fetchall()]
for c in df.columns:
    if c not in existing_cols:
        # Use TEXT as a safe default; refine types later if you want
        con.execute(f'ALTER TABLE posts ADD COLUMN "{c}" TEXT')

# Build a MERGE that does an upsert by id
cols = list(df.columns)

# LHS must be UNqualified in UPDATE SET (DuckDB quirk), RHS qualified to source.
assignments = ", ".join([f'"{c}" = source."{c}"' for c in cols if c != "id"])

# For INSERT, target column list is unqualified, VALUES must come from source.*
cols_unq = ", ".join(f'"{c}"' for c in cols)
cols_src = ", ".join(f'source."{c}"' for c in cols)

con.execute(f"""
MERGE INTO posts AS target
USING df_new  AS source
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET {assignments}
WHEN NOT MATCHED THEN INSERT ({cols_unq}) VALUES ({cols_src});
""")

# Optional: parsed timestamp column for nicer ordering
con.execute("""
ALTER TABLE posts ADD COLUMN IF NOT EXISTS ts TIMESTAMP;
UPDATE posts
SET ts = COALESCE(
  try_strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ'),
  try_strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
)
WHERE ts IS NULL AND timestamp IS NOT NULL;
""")

rows = con.execute("""
SELECT id, ownerUsername, "type", timestamp
FROM posts
ORDER BY COALESCE(ts, now()) DESC
LIMIT 8
""").fetchall()
print("rows:", len(rows))
print(rows)

con.close()
