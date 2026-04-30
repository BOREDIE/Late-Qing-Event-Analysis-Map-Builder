#!/usr/bin/env python3
"""
test_qing.py
------------
Non-interactive test: run the full pipeline on 清末民变年表_数据集_geo.xlsx.
Produces output/qing_event_map.html in the project folder.
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from src.utils       import load_events
from src.geo_lookup  import GeoLookup
from src.map_builder import MapBuilder

# ── paths ─────────────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT = os.path.dirname(_HERE)

DATA_PATH  = os.path.join(_PROJ_ROOT, "清末民变年表_数据集_geo.xlsx")
CHGIS_PATH = os.path.join(_PROJ_ROOT, "1911 Layers UTF8 Encoding", "extracted")
OUT_PATH   = os.path.join(_HERE, "output", "qing_event_map.html")

# ── column mapping for 清末民变年表_数据集_geo.xlsx ───────────────────────────
COL_MAP = dict(
    prov_col = "prov_ch",    # province   e.g. "安徽省"
    pref_col = "pref_ch",    # prefecture e.g. "太平府"
    cnty_col = None,         # no county column in this dataset
)

POPUP_COLS = [
    "公历年", "月份(公历)", "公历日",
    "省份/地区", "事件类型", "事件描述",
    "pref_ch", "circuit_ch", "prov_ch",
]

COLOR_COL = "事件类型"
TITLE     = "清末民变地图 1902–1911  ·  Late Qing Popular Uprisings"


# ── run ───────────────────────────────────────────────────────────────────────
def run():
    print("=== test_qing.py ===\n")

    # 1. Load
    print(f"Loading {DATA_PATH} …")
    df = load_events(DATA_PATH)
    print(f"  {len(df)} rows loaded.")

    # 2. Filter to rows that have popup content
    popup_cols = [c for c in POPUP_COLS if c in df.columns]

    # 3. Geocode
    print(f"Loading CHGIS from {CHGIS_PATH} …")
    geo = GeoLookup(CHGIS_PATH)

    print("Geocoding …")
    df_geo = geo.geocode_dataframe(df, **COL_MAP)

    matched = df_geo["_lat"].notna().sum()
    print(f"  Geocoded: {matched} / {len(df_geo)}")
    print(df_geo["_geo_level"].value_counts().to_string())

    # 4. Build map
    print("\nBuilding map …")
    builder = MapBuilder(CHGIS_PATH)
    m = builder.build(
        df_geo,
        popup_cols=popup_cols,
        color_col=COLOR_COL,
        title=TITLE,
        heat_radius=18,
        heat_blur=14,
    )

    # 5. Save
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    m.save(OUT_PATH)
    print(f"\nSaved → {OUT_PATH}")


if __name__ == "__main__":
    run()
