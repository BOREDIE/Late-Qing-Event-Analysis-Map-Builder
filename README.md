# Qing Event Map Pipeline

Transform any historical events dataset with geographic columns into an
interactive dual-layer HTML map — **dot map** and **heat map** —
anchored to the **CHGIS 1911** administrative-boundary shapefiles.

------------------------------------------------------------------------

## Features

| Feature | Detail |
|------------------------------------|------------------------------------|
| Three-level geocoding | Province → Prefecture → County (uses most specific available) |
| Missing levels OK | Any geographic level can be omitted; the map still works |
| Dual-layer toggle | One-click switch between **Dot Map** (individual events + popups) and **Heat Map** (density) |
| Three-level boundaries | Province / Prefecture / County polygon overlays, independently toggleable |
| Colour coding | Dot colours driven by any categorical column (e.g. event type) |
| Three base tiles | CartoDB Light / OpenStreetMap / CartoDB Dark |
| Universal input | Accepts `.xlsx` or `.csv` |

------------------------------------------------------------------------

## Required folder layout

This pipeline must sit **inside** the research project folder alongside
the CHGIS data. The expected layout is:

```         
<project root>/
├── 1911 Layers UTF8 Encoding/
│   └── extracted/                  ← CHGIS shapefiles go here
│       ├── v6_1911_prov_pgn_utf/
│       ├── v6_1911_prov_pts_utf/
│       ├── v6_1911_pref_pgn_utf/
│       ├── v6_1911_pref_pts_utf/
│       ├── v6_1911_cnty_pgn_utf/
│       ├── v6_1911_cnty_pts_utf/
│       └── v6_1911_twn_pts_utf/
└── qing-event-map/                 ← this folder
    ├── pipeline.py
    ├── test_qing.py
    ├── output/                     ← generated HTML maps saved here
    └── src/
```

The pipeline automatically resolves the default CHGIS path as
`../1911 Layers UTF8 Encoding/extracted` relative to its own location,
so **no configuration is needed** as long as the folder layout above is
followed.

To use a different location, pass `--chgis /your/path` on the command
line.

------------------------------------------------------------------------

## Installation

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## Usage

### Interactive (recommended for new datasets)

``` bash
python pipeline.py
```

The pipeline will: 1. Ask for your data file path 2. Display all columns
with sample values 3. Ask you to identify the province, prefecture, and
county columns (press **Enter** to skip any level) 4. Ask which columns
to show in popups 5. Ask which column to use for dot colour-coding
(optional) 6. Geocode and produce the HTML map

The output HTML file is saved to `output/` inside this folder by
default.

### Non-interactive (scripted / reproducible)

``` bash
python pipeline.py \
  --data  /path/to/events.xlsx \
  --prov  "province_column" \
  --pref  "prefecture_column" \
  --cnty  "county_column" \
  --popup "year,month,type,description" \
  --color "event_type" \
  --title "My Historical Events" \
  --out   output/my_map.html
```

All `--prov`, `--pref`, `--cnty` are optional — omit any level that
doesn't exist in your dataset.

------------------------------------------------------------------------

## Data format

Your dataset must have **at least one** geographic column containing
historical administrative names that match the CHGIS 1911 register:

| Level      | Example values               | CHGIS match source     |
|------------|------------------------------|------------------------|
| Province   | `安徽省`, `直隶省`, `Anhui`  | `v6_1911_prov_pts_utf` |
| Prefecture | `太平府`, `宁波府`, `扬州府` | `v6_1911_pref_pts_utf` |
| County     | `铜陵县`, `广宗县`           | `v6_1911_cnty_pts_utf` |

Columns that hold other information (dates, descriptions, event types)
are shown in the popup and can be used for colour-coding.

------------------------------------------------------------------------

## Output

A single self-contained HTML file (\~5–15 MB depending on event count),
saved to the `output/` folder inside `qing-event-map/`.

**Controls:** - `● Dot Map` / `🔥 Heat Map` — mutually exclusive
event-view toggle (top-left panel) - `🟧 Province` / `🟦 Prefecture` /
`🟩 County` — independent boundary toggles (top-left panel) - Layer
control panel (top-right) — base tile switcher - Click any dot for the
popup with full event details

------------------------------------------------------------------------

## Testing with the Qing uprising dataset

``` bash
python test_qing.py
```

This runs the pipeline non-interactively on
`清末民变年表_数据集_geo.xlsx` using province (`prov` / `prov_ch`) and prefecture
(`pref` / `pref_ch`) columns and saves to `output/qing_event_map.html`.

------------------------------------------------------------------------

## Data citation

The boundary shapefiles are from the **China Historical Geographic
Information System (CHGIS) Version 6**, published by Harvard Dataverse.

> CHGIS. *1911 Layers UTF8 Encoding* [Dataset]. V1. Harvard Dataverse,
> 2016. <https://doi.org/10.7910/DVN/HHVVHX>

Full citation (from `../doi_10.7910_DVN_HHVVHX.xml`):

| Field     | Value                                                    |
|-----------|----------------------------------------------------------|
| Author    | CHGIS                                                    |
| Title     | 1911 Layers UTF8 Encoding                                |
| Publisher | Harvard Dataverse                                        |
| Year      | 2016                                                     |
| Edition   | V1                                                       |
| DOI       | [10.7910/DVN/HHVVHX](https://doi.org/10.7910/DVN/HHVVHX) |
