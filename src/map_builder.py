"""
map_builder.py
--------------
Build a dual-layer (dot map + heat map) Folium HTML map with
three-level 1911 CHGIS administrative boundaries as switchable context.

Interface layout
----------------
  Top-left panel:
    • Title + event count
    • EVENT VIEW  — [● Dot Map]  [🔥 Heat Map]  (mutually exclusive toggle)
    • BOUNDARIES  — [🟧 Province] [🟦 Prefecture] [🟩 County] (independent toggles)
    • Event-type colour legend
  Top-right:
    • Standard Leaflet LayerControl (base tiles; all layers also listed here)
"""

import warnings
import textwrap
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap, MarkerCluster

# ── event-type colour palette ─────────────────────────────────────────────────
_PALETTE = [
    "#e05c5c", "#e09b5c", "#d4c830", "#5cba5c", "#5cb8e0",
    "#5c7ae0", "#a05ce0", "#e05cb8", "#999999",
]

def _event_color_map(series: pd.Series) -> dict[str, str]:
    vals = [v for v in series.dropna().unique() if str(v) not in ("nan", "None", "")]
    return {v: _PALETTE[i % len(_PALETTE)] for i, v in enumerate(vals)}


def _popup_html(row: pd.Series, cols: list[str]) -> str:
    cells = ""
    for c in cols:
        val = row.get(c)
        if val is None or str(val) in ("nan", "None", ""):
            continue
        text = str(val)
        if len(text) > 220:
            text = text[:220] + "…"
        cells += (
            f"<tr><td style='padding:2px 7px;color:#777;font-size:11px'>{c}</td>"
            f"<td style='padding:2px 7px;font-size:12px'>{text}</td></tr>"
        )
    return f"<table style='border-collapse:collapse;max-width:380px'>{cells}</table>"


def _prep_gdf(gdf: gpd.GeoDataFrame, keep_cols: list[str]) -> gpd.GeoDataFrame:
    """Select columns (deduped), fill NaN → '', return copy."""
    seen: set[str] = set()
    unique: list[str] = []
    for c in keep_cols:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    cols = [c for c in unique if c in gdf.columns] + ["geometry"]
    out  = gdf[cols].copy()
    for c in cols:
        if c != "geometry":
            out[c] = out[c].fillna("").astype(str)
    return out


# ── boundary layer styling ────────────────────────────────────────────────────
_STYLES = {
    "province":   dict(fillColor="#e8a87c", color="#8b4513", weight=1.8, fillOpacity=0.25),
    "prefecture": dict(fillColor="#7ec8e3", color="#1a5276", weight=0.9, fillOpacity=0.18),
    "county":     dict(fillColor="#a8d8a8", color="#1e8449", weight=0.5, fillOpacity=0.12),
}
_HIGHLIGHT = dict(fillOpacity=0.55, weight=2.5)

def _style_fn(level: str):
    s = _STYLES[level]
    return lambda f: s

def _hl_fn(level: str):
    h = {**_STYLES[level], **_HIGHLIGHT}
    return lambda f: h


class MapBuilder:
    """
    Parameters
    ----------
    chgis_base : str
        Path to the 'extracted' CHGIS 1911 folder.
    """

    def __init__(self, chgis_base: str):
        self._base = chgis_base

        print("  Loading boundary shapefiles …")
        self._prov_pgn = self._load_pgn(
            "v6_1911_prov_pgn_utf/v6_1911_prov_pgn_utf.shp", tol=0.02
        )
        self._pref_pgn = self._load_pgn(
            "v6_1911_pref_pgn_utf/v6_1911_pref_pgn_utf.shp", tol=0.01
        )
        self._cnty_pgn = self._load_pgn(
            "v6_1911_cnty_pgn_utf/v6_1911_cnty_pgn_utf.shp", tol=0.005
        )
        print(f"    province: {len(self._prov_pgn)} | "
              f"prefecture: {len(self._pref_pgn)} | "
              f"county: {len(self._cnty_pgn)}")

    # ── private ───────────────────────────────────────────────────────────────

    def _load_pgn(self, rel: str, tol: float):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = gpd.read_file(f"{self._base}/{rel}", encoding="utf-8")
        gdf = gdf.to_crs("EPSG:4326")
        gdf["geometry"] = gdf["geometry"].simplify(tol, preserve_topology=True)
        return gdf

    def _boundary_layer(
        self,
        gdf: gpd.GeoDataFrame,
        level: str,
        name: str,
        tooltip_fields: list[str],
        popup_fields: list[str],
        show: bool,
    ) -> folium.FeatureGroup:
        """Build a single boundary FeatureGroup using a batched GeoJson call."""
        clean = _prep_gdf(gdf, tooltip_fields + popup_fields)

        layer = folium.FeatureGroup(name=name, show=show)
        folium.GeoJson(
            clean,
            name=name,
            style_function=_style_fn(level),
            highlight_function=_hl_fn(level),
            tooltip=folium.GeoJsonTooltip(
                fields=[f for f in tooltip_fields if f in clean.columns],
                aliases=[f for f in tooltip_fields if f in clean.columns],
                localize=True,
                sticky=False,
            ),
            popup=folium.GeoJsonPopup(
                fields=[f for f in popup_fields if f in clean.columns],
                aliases=[f for f in popup_fields if f in clean.columns],
                localize=True,
                max_width=340,
            ),
        ).add_to(layer)
        return layer

    # ── public ────────────────────────────────────────────────────────────────

    def build(
        self,
        df: pd.DataFrame,
        popup_cols: list[str],
        color_col: str | None = None,
        title: str = "Historical Events Map",
        heat_radius: int = 18,
        heat_blur: int = 14,
    ) -> folium.Map:
        """
        Build and return a Folium map.

        Parameters
        ----------
        df : DataFrame
            Must contain '_lat' and '_lon' columns (added by GeoLookup).
        popup_cols : list[str]
            Columns shown in the dot-map popup.
        color_col : str | None
            Column for dot colour-coding (e.g. event type).
        title : str
            Map title shown in the info panel.
        heat_radius / heat_blur : int
            HeatMap parameters.
        """
        geo = df.dropna(subset=["_lat", "_lon"]).copy()

        m = folium.Map(location=[35.5, 105.0], zoom_start=5, tiles=None)

        # ── base tiles ────────────────────────────────────────────────────────
        folium.TileLayer("CartoDB positron",    name="Light (CartoDB)",  control=True).add_to(m)
        folium.TileLayer("OpenStreetMap",       name="OpenStreetMap",    control=True).add_to(m)
        folium.TileLayer("CartoDB dark_matter", name="Dark (CartoDB)",   control=True).add_to(m)

        # ── boundary layers ───────────────────────────────────────────────────
        prov_layer = self._boundary_layer(
            self._prov_pgn, "province",
            name="🟧 Province  省",
            tooltip_fields=["NAME_PY", "NAME_CH", "TYPE_CH", "DYN_CH"],
            popup_fields=["NAME_PY", "NAME_CH", "NAME_FT",
                          "TYPE_CH", "DYN_CH", "BEG_YR", "END_YR"],
            show=True,
        )
        pref_layer = self._boundary_layer(
            self._pref_pgn, "prefecture",
            name="🟦 Prefecture  府/州/厅",
            tooltip_fields=["NAME_PY", "NAME_CH", "TYPE_CH", "LEV1_CH"],
            popup_fields=["NAME_PY", "NAME_CH", "NAME_FT",
                          "TYPE_CH", "LEV1_CH", "DYN_CH", "BEG_YR", "END_YR"],
            show=False,
        )
        cnty_layer = self._boundary_layer(
            self._cnty_pgn, "county",
            name="🟩 County  县",
            tooltip_fields=["NAME_PY", "NAME_CH", "TYPE_CH", "LEV2_CH", "LEV1_CH"],
            popup_fields=["NAME_PY", "NAME_CH", "NAME_FT",
                          "TYPE_CH", "LEV2_CH", "LEV1_CH", "DYN_CH", "BEG_YR", "END_YR"],
            show=False,
        )
        prov_layer.add_to(m)
        pref_layer.add_to(m)
        cnty_layer.add_to(m)

        # ── colour map ────────────────────────────────────────────────────────
        color_map: dict[str, str] = {}
        if color_col and color_col in geo.columns:
            color_map = _event_color_map(geo[color_col])

        def dot_color(row):
            if color_col and color_col in row and str(row[color_col]) in color_map:
                return color_map[str(row[color_col])]
            return "#c0392b"

        # ── dot map ───────────────────────────────────────────────────────────
        dot_group = folium.FeatureGroup(name="● Dot Map", show=True)
        cluster   = MarkerCluster(options={"maxClusterRadius": 35}).add_to(dot_group)

        for _, row in geo.iterrows():
            c = dot_color(row)
            folium.CircleMarker(
                location=[row["_lat"], row["_lon"]],
                radius=6,
                color=c, fill=True, fill_color=c, fill_opacity=0.78, weight=1.2,
                popup=folium.Popup(_popup_html(row, popup_cols), max_width=400),
                tooltip=folium.Tooltip(
                    str(row.get(popup_cols[0], "")) if popup_cols else ""
                ),
            ).add_to(cluster)
        dot_group.add_to(m)

        # ── heat map ──────────────────────────────────────────────────────────
        heat_group = folium.FeatureGroup(name="🔥 Heat Map", show=False)
        HeatMap(
            [[r["_lat"], r["_lon"], 1.0] for _, r in geo.iterrows()],
            radius=heat_radius,
            blur=heat_blur,
            gradient={0.25: "#3050e0", 0.5: "#30d080", 0.75: "#f0d000", 1.0: "#e02020"},
        ).add_to(heat_group)
        heat_group.add_to(m)

        # ── layer control ─────────────────────────────────────────────────────
        folium.LayerControl(collapsed=False).add_to(m)

        # ── retrieve JS variable names ────────────────────────────────────────
        map_var  = m.get_name()
        dot_var  = dot_group.get_name()
        heat_var = heat_group.get_name()
        prov_var = prov_layer.get_name()
        pref_var = pref_layer.get_name()
        cnty_var = cnty_layer.get_name()

        # ── event-type legend HTML ────────────────────────────────────────────
        legend_html = "".join(
            f"<span style='display:inline-block;width:10px;height:10px;"
            f"border-radius:50%;background:{c};margin-right:3px;vertical-align:middle'>"
            f"</span><span style='font-size:11px;margin-right:8px'>{k}</span>"
            for k, c in list(color_map.items())[:12]
        )

        skipped = len(df) - len(geo)

        panel_html = textwrap.dedent(f"""
        <!-- ═══ info panel ═══════════════════════════════════════════════════ -->
        <div id="info-panel" style="
            position:fixed;top:10px;left:60px;z-index:9999;
            background:rgba(255,255,255,0.96);padding:14px 18px;
            border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.22);
            font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
            max-width:370px;min-width:260px">

          <!-- title -->
          <div style="font-size:15px;font-weight:700;color:#2c1a06">{title}</div>
          <div style="font-size:12px;color:#666;margin-top:3px">
            {len(geo)} events mapped
            {'&nbsp;·&nbsp;<span style="color:#c0392b">' + str(skipped) + ' skipped</span>' if skipped else ''}
          </div>

          <hr style="margin:9px 0;border:none;border-top:1px solid #e4e4e4">

          <!-- ── EVENT VIEW ─────────────────────────────────────────────── -->
          <div style="font-size:10px;font-weight:700;color:#999;
                      letter-spacing:.08em;margin-bottom:5px">EVENT VIEW</div>
          <div style="display:flex;gap:7px">
            <button id="btn-dot" onclick="showDotMap()" style="
                flex:1;padding:6px 4px;border:2px solid #c0392b;border-radius:5px;
                background:#c0392b;color:#fff;font-size:12px;font-weight:600;
                cursor:pointer">● Dot Map</button>
            <button id="btn-heat" onclick="showHeatMap()" style="
                flex:1;padding:6px 4px;border:2px solid #ccc;border-radius:5px;
                background:#fff;color:#666;font-size:12px;font-weight:600;
                cursor:pointer">🔥 Heat Map</button>
          </div>

          <hr style="margin:9px 0;border:none;border-top:1px solid #e4e4e4">

          <!-- ── BOUNDARIES ────────────────────────────────────────────── -->
          <div style="font-size:10px;font-weight:700;color:#999;
                      letter-spacing:.08em;margin-bottom:5px">BOUNDARIES</div>
          <div style="display:flex;gap:7px">
            <button id="btn-prov" onclick="toggleBoundary('prov')" style="
                flex:1;padding:5px 3px;border:2px solid #8b4513;border-radius:5px;
                background:#e8a87c;color:#fff;font-size:11px;font-weight:600;
                cursor:pointer">🟧 Province</button>
            <button id="btn-pref" onclick="toggleBoundary('pref')" style="
                flex:1;padding:5px 3px;border:2px solid #ccc;border-radius:5px;
                background:#fff;color:#666;font-size:11px;font-weight:600;
                cursor:pointer">🟦 Prefecture</button>
            <button id="btn-cnty" onclick="toggleBoundary('cnty')" style="
                flex:1;padding:5px 3px;border:2px solid #ccc;border-radius:5px;
                background:#fff;color:#666;font-size:11px;font-weight:600;
                cursor:pointer">🟩 County</button>
          </div>

          {'<hr style="margin:9px 0;border:none;border-top:1px solid #e4e4e4"><div style="line-height:1.9">' + legend_html + '</div>' if legend_html else ''}

          <div style="font-size:10px;color:#bbb;margin-top:7px">
            Click a dot for details &nbsp;·&nbsp; Layer panel ↗ for base tiles
          </div>
        </div>

        <!-- ═══ JavaScript ════════════════════════════════════════════════════ -->
        <script>
        (function () {{
            function ready(fn) {{
                if (document.readyState !== 'loading') fn();
                else document.addEventListener('DOMContentLoaded', fn);
            }}

            ready(function () {{
                var mapObj  = {map_var};
                var dotL    = {dot_var};
                var heatL   = {heat_var};
                var provL   = {prov_var};
                var prefL   = {pref_var};
                var cntyL   = {cnty_var};

                /* ── active state for a given button ── */
                var btnStyles = {{
                    'btn-dot':  {{ on: {{bg:'#c0392b', bdr:'#c0392b', fg:'#fff'}},
                                   off:{{bg:'#fff',    bdr:'#ccc',    fg:'#666'}} }},
                    'btn-heat': {{ on: {{bg:'#e05c1e', bdr:'#e05c1e', fg:'#fff'}},
                                   off:{{bg:'#fff',    bdr:'#ccc',    fg:'#666'}} }},
                    'btn-prov': {{ on: {{bg:'#e8a87c', bdr:'#8b4513', fg:'#fff'}},
                                   off:{{bg:'#fff',    bdr:'#ccc',    fg:'#666'}} }},
                    'btn-pref': {{ on: {{bg:'#7ec8e3', bdr:'#1a5276', fg:'#fff'}},
                                   off:{{bg:'#fff',    bdr:'#ccc',    fg:'#666'}} }},
                    'btn-cnty': {{ on: {{bg:'#a8d8a8', bdr:'#1e8449', fg:'#fff'}},
                                   off:{{bg:'#fff',    bdr:'#ccc',    fg:'#666'}} }},
                }};

                function setBtn(id, active) {{
                    var btn = document.getElementById(id);
                    var st  = btnStyles[id][active ? 'on' : 'off'];
                    btn.style.background   = st.bg;
                    btn.style.borderColor  = st.bdr;
                    btn.style.color        = st.fg;
                }}

                /* ── event view toggle (mutually exclusive) ── */
                window.showDotMap = function () {{
                    mapObj.addLayer(dotL);
                    mapObj.removeLayer(heatL);
                    setBtn('btn-dot',  true);
                    setBtn('btn-heat', false);
                }};

                window.showHeatMap = function () {{
                    mapObj.addLayer(heatL);
                    mapObj.removeLayer(dotL);
                    setBtn('btn-heat', true);
                    setBtn('btn-dot',  false);
                }};

                /* ── boundary toggles (independent) ── */
                var boundaryState = {{ prov: true, pref: false, cnty: false }};
                var boundaryLayer = {{ prov: provL, pref: prefL, cnty: cntyL }};
                var boundaryBtn   = {{ prov: 'btn-prov', pref: 'btn-pref', cnty: 'btn-cnty' }};

                window.toggleBoundary = function (key) {{
                    var layer = boundaryLayer[key];
                    var on    = !boundaryState[key];
                    boundaryState[key] = on;
                    if (on) mapObj.addLayer(layer);
                    else    mapObj.removeLayer(layer);
                    setBtn(boundaryBtn[key], on);
                }};

                /* ── sync initial button states ── */
                setBtn('btn-dot',  true);
                setBtn('btn-heat', false);
                setBtn('btn-prov', true);
                setBtn('btn-pref', false);
                setBtn('btn-cnty', false);
            }});
        }})();
        </script>
        """)

        m.get_root().html.add_child(folium.Element(panel_html))
        return m
