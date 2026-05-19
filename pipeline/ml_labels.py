"""ML labels — binary MCI label per stop × hour bin × day_type.

SDLC §5.3: 64 bins = 16 night hours (17-8) × 4 day_types.
Binary label: 1 if any MCI incident within 250m at that hour in last 36mo.
Output: data/gold/labels.parquet
"""
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
GOLD = ROOT / "data" / "gold"
SILVER = ROOT / "data" / "silver"
GOLD.mkdir(parents=True, exist_ok=True)

HOURS = list(range(17, 24)) + list(range(0, 9))  # 17-23, 0-8
DAY_TYPES = {"weekday": "Mon-Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
LABEL_PATH = GOLD / "labels.parquet"

SQL = r"""
-- Stops
CREATE OR REPLACE TABLE stops AS
SELECT uid, stop_id, stop_name, stop_lat, stop_lon
FROM read_parquet('{gold}/stop_features.parquet');

-- Crime within 250m (already night-filtered in bronze, silver deduped)
CREATE OR REPLACE TABLE crime AS
SELECT lat, lon, occ_hour, day_type, mci_category, event_id
FROM read_parquet('{silver}/crime.parquet')
WHERE lat IS NOT NULL AND lon IS NOT NULL;

-- Cross join stops × bins with coords, then LEFT JOIN crime per bin
CREATE OR REPLACE TABLE bins AS
SELECT s.uid, s.stop_lat, s.stop_lon, h.hour, d.day_type
FROM stops s
CROSS JOIN (SELECT unnest([17,18,19,20,21,22,23,0,1,2,3,4,5,6,7,8]) AS hour) h
CROSS JOIN (SELECT unnest(['weekday','fri','sat','sun']) AS day_type) d;

-- Spatial join: crime within 250m per bin
CREATE OR REPLACE TABLE labels AS
SELECT b.uid, b.hour, b.day_type,
       COUNT(c.event_id) AS mci_count,
       CASE WHEN COUNT(c.event_id) > 0 THEN 1 ELSE 0 END AS label
FROM bins b
LEFT JOIN crime c ON
    c.occ_hour = b.hour
    AND c.day_type = b.day_type
    AND c.lat BETWEEN b.stop_lat - 0.004 AND b.stop_lat + 0.004
    AND c.lon BETWEEN b.stop_lon - 0.005 AND b.stop_lon + 0.005
GROUP BY b.uid, b.hour, b.day_type;

-- Merge stop info back
COPY (
    SELECT l.*, s.stop_id, s.stop_name, s.stop_lat, s.stop_lon
    FROM labels l
    JOIN stops s ON l.uid = s.uid
) TO '{out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
"""


def main() -> int:
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")

    sql = SQL.format(gold=str(GOLD), silver=str(SILVER), out=str(LABEL_PATH))
    con.execute(sql)
    con.close()

    df = pd.read_parquet(LABEL_PATH)
    print(f"Labels: {len(df):,} rows, {df['label'].sum():,} positives "
          f"({df['label'].mean()*100:.1f}%)")
    print(f"Bins with >0 labels: {df.groupby(['hour','day_type'])['label'].sum().gt(0).sum()}/{len(HOURS)*len(DAY_TYPES)}")
    print(f"  -> {LABEL_PATH} ({LABEL_PATH.stat().st_size/1024:.0f} KB)")

    # Bin sparsity check
    bin_counts = df.groupby(["hour", "day_type"])["label"].agg(["sum", "count"])
    bin_counts["rate"] = bin_counts["sum"] / bin_counts["count"]
    print("\nSparsest bins (lowest positive rate):")
    for (h, dt), r in bin_counts.nsmallest(5, "rate").iterrows():
        print(f"  hour={h:2d} {dt:7s}: {int(r['sum']):,} pos / {int(r['count']):,} = {r['rate']:.4f}")

    return 0


if __name__ == "__main__":
    import sys; sys.exit(main())
