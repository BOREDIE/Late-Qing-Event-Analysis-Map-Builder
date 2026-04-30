#!/usr/bin/env python3
"""
pipeline.py
-----------
Entry point for the Qing Event Map pipeline.

Interactive usage:
    python pipeline.py

With arguments (non-interactive):
    python pipeline.py \\
        --data    /path/to/events.xlsx \\
        --chgis   /path/to/extracted \\
        --out     /path/to/output.html \\
        --prov    1adm_ch \\
        --pref    3adm_ch \\
        --popup   "公历年,月份(公历),省份/地区,事件类型,事件描述" \\
        --color   事件类型 \\
        --title   "Late Qing Uprisings 1902-1911"
"""

import argparse
import os
import sys

# ── make sure src/ is importable when running from the project root ───────────
sys.path.insert(0, os.path.dirname(__file__))

from src.utils      import load_events, prompt_column_mapping, infer_columns
from src.geo_lookup import GeoLookup
from src.map_builder import MapBuilder


# ── default paths (project-relative; override via CLI) ───────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT = os.path.dirname(_HERE)               # one level up from qing-event-map/

DEFAULT_CHGIS = os.path.join(
    _PROJ_ROOT,
    "1911 Layers UTF8 Encoding", "extracted",
)
DEFAULT_OUT = os.path.join(_HERE, "output", "event_map.html")


# ── argument parser ───────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a dual-layer (dot + heat) event map from a "
                    "CSV/Excel dataset, anchored to CHGIS 1911 shapefiles.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("--data",  metavar="PATH", help="Events file (.xlsx or .csv)")
    p.add_argument("--chgis", metavar="PATH", default=DEFAULT_CHGIS,
                   help=f"CHGIS extracted folder\n[default: {DEFAULT_CHGIS}]")
    p.add_argument("--out",   metavar="PATH", default=DEFAULT_OUT,
                   help=f"Output HTML path\n[default: {DEFAULT_OUT}]")
    p.add_argument("--prov",  metavar="COL",  help="Province column name")
    p.add_argument("--pref",  metavar="COL",  help="Prefecture column name")
    p.add_argument("--cnty",  metavar="COL",  help="County column name")
    p.add_argument("--popup", metavar="COLS",
                   help="Comma-separated popup column names")
    p.add_argument("--color", metavar="COL",
                   help="Column for dot colour-coding")
    p.add_argument("--title", metavar="TEXT",
                   default="Historical Events Map",
                   help="Map title")
    p.add_argument("--heat-radius", type=int, default=18, metavar="N")
    p.add_argument("--heat-blur",   type=int, default=14, metavar="N")
    return p


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    args = _build_parser().parse_args()

    # ── 1. load data ──────────────────────────────────────────────────────────
    if args.data:
        data_path = args.data
    else:
        print("=== Qing Event Map Pipeline ===\n")
        data_path = input("Events file (.xlsx / .csv): ").strip().strip("'\"")

    print(f"\nLoading {data_path} …")
    df = load_events(data_path)
    print(f"  {len(df)} rows × {len(df.columns)} columns loaded.")

    # ── 2. column mapping ─────────────────────────────────────────────────────
    if args.prov or args.pref or args.cnty:
        # non-interactive: columns provided on CLI
        prov_col   = args.prov  if args.prov  and args.prov  in df.columns else None
        pref_col   = args.pref  if args.pref  and args.pref  in df.columns else None
        cnty_col   = args.cnty  if args.cnty  and args.cnty  in df.columns else None
        popup_cols = (
            [c.strip() for c in args.popup.split(",") if c.strip() in df.columns]
            if args.popup else
            [c for c in df.columns if c not in {prov_col, pref_col, cnty_col}]
        )
        color_col  = args.color if args.color and args.color in df.columns else None
    else:
        # interactive: ask the user
        inferred = infer_columns(df)
        if any(inferred.values()):
            print(f"\nAuto-detected columns: {inferred}")
            answer = input("Use these automatically? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                prov_col  = inferred["prov_col"]
                pref_col  = inferred["pref_col"]
                cnty_col  = inferred["cnty_col"]
                popup_cols = [
                    c for c in df.columns
                    if c not in {prov_col, pref_col, cnty_col}
                ]
                color_col = None
            else:
                mapping   = prompt_column_mapping(df)
                prov_col  = mapping["prov_col"]
                pref_col  = mapping["pref_col"]
                cnty_col  = mapping["cnty_col"]
                popup_cols = mapping["popup_cols"]
                color_col  = mapping["color_col"]
        else:
            mapping   = prompt_column_mapping(df)
            prov_col  = mapping["prov_col"]
            pref_col  = mapping["pref_col"]
            cnty_col  = mapping["cnty_col"]
            popup_cols = mapping["popup_cols"]
            color_col  = mapping["color_col"]

    print(f"\nColumn mapping:")
    print(f"  Province   → {prov_col or '(skipped)'}")
    print(f"  Prefecture → {pref_col or '(skipped)'}")
    print(f"  County     → {cnty_col or '(skipped)'}")
    print(f"  Popup cols → {popup_cols}")
    print(f"  Color by   → {color_col or '(none)'}")

    # ── 3. geocode ────────────────────────────────────────────────────────────
    chgis_path = args.chgis
    if not os.path.isdir(chgis_path):
        print(f"\n✗ CHGIS path not found: {chgis_path}")
        chgis_path = input("Enter CHGIS extracted folder path: ").strip().strip("'\"")

    print(f"\nLoading CHGIS shapefiles from {chgis_path} …")
    geo = GeoLookup(chgis_path)

    print("Geocoding events …")
    df_geo = geo.geocode_dataframe(df, prov_col=prov_col, pref_col=pref_col, cnty_col=cnty_col)

    matched = df_geo["_lat"].notna().sum()
    skipped = len(df_geo) - matched
    print(f"  Geocoded : {matched} / {len(df_geo)}")
    if skipped:
        print(f"  Skipped  : {skipped} (no coordinates found)")

    level_counts = df_geo["_geo_level"].value_counts()
    for level, count in level_counts.items():
        print(f"    {level:12s}: {count}")

    # ── 4. build map ──────────────────────────────────────────────────────────
    print("\nBuilding map …")
    builder = MapBuilder(chgis_path)
    m = builder.build(
        df_geo,
        popup_cols=popup_cols,
        color_col=color_col,
        title=args.title,
        heat_radius=args.heat_radius,
        heat_blur=args.heat_blur,
    )

    # ── 5. save ───────────────────────────────────────────────────────────────
    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    m.save(out_path)
    print(f"\nSaved → {out_path}")
    return out_path


if __name__ == "__main__":
    main()
