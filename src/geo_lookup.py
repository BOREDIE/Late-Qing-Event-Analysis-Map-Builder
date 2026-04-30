"""
geo_lookup.py
-------------
Geocode historical event rows using CHGIS 1911 point shapefiles.

Priority: county-level > prefecture-level > province-level
"""

import re
import warnings
import pandas as pd
import geopandas as gpd

# Chinese suffix stripping (bare-name fallbacks for Chinese input)
_SFXS_PREF = re.compile(r"[府州厅]$")
_SFXS_CNTY = re.compile(r"[县厅州]$")

# Pinyin suffix stripping (bare-name fallbacks for English/Pinyin input)
# Prefecture suffixes: Fu (府), Zhou (州), Ting (厅)
# County suffixes   : Xian (县), Qi (旗), Zhou (直隶州), Ting (厅)
_PY_SFX_PREF = re.compile(r"\s+(Fu|Zhou|Ting)$", re.IGNORECASE)
_PY_SFX_CNTY = re.compile(r"\s+(Xian|Qi|Zhou|Ting)$", re.IGNORECASE)


class GeoLookup:
    """
    Load CHGIS 1911 point layers and expose fast name → (lat, lon) lookups.

    Parameters
    ----------
    chgis_base : str
        Path to the 'extracted' folder produced by unzipping the 1911 UTF-8
        shapefiles, e.g. '.../1911 Layers UTF8 Encoding/extracted'.
    """

    def __init__(self, chgis_base: str):
        self._prov: dict[str, tuple[float, float]] = {}
        self._pref: dict[str, tuple[float, float]] = {}
        self._cnty: dict[str, tuple[float, float]] = {}
        self._load(chgis_base)

    # ── private ───────────────────────────────────────────────────────────────

    def _load(self, base: str):
        def read(rel):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gdf = gpd.read_file(f"{base}/{rel}", encoding="utf-8")
            return gdf.to_crs("EPSG:4326")

        prov_pts = read("v6_1911_prov_pts_utf/v6_1911_prov_pts_utf.shp")
        pref_pts = read("v6_1911_pref_pts_utf/v6_1911_pref_pts_utf.shp")
        cnty_pts = read("v6_1911_cnty_pts_utf/v6_1911_cnty_pts_utf.shp")

        for _, row in prov_pts.iterrows():
            name = str(row["NAME_CH"])
            coord = (row.geometry.y, row.geometry.x)
            self._prov[name] = coord
            self._prov[name + "省"] = coord        # "安徽" → also match "安徽省"
            py = str(row.get("NAME_PY", "") or "").strip()
            if py:
                self._prov[py] = coord             # "Jiangsu"
                self._prov[py.lower()] = coord     # "jiangsu"

        for _, row in pref_pts.iterrows():
            name = str(row["NAME_CH"])
            coord = (row.geometry.y, row.geometry.x)
            self._pref[name] = coord
            bare_ch = _SFXS_PREF.sub("", name)
            if len(bare_ch) >= 2:
                self._pref.setdefault(bare_ch, coord)
            py = str(row.get("NAME_PY", "") or "").strip()
            if py:
                self._pref[py] = coord             # "Xuzhou Fu"
                self._pref[py.lower()] = coord     # "xuzhou fu"
                bare_py = _PY_SFX_PREF.sub("", py).strip()
                if bare_py != py:
                    self._pref.setdefault(bare_py, coord)        # "Xuzhou"
                    self._pref.setdefault(bare_py.lower(), coord) # "xuzhou"

        for _, row in cnty_pts.iterrows():
            name = str(row["NAME_CH"])
            coord = (row.geometry.y, row.geometry.x)
            self._cnty[name] = coord
            bare_ch = _SFXS_CNTY.sub("", name)
            if len(bare_ch) >= 2:
                self._cnty.setdefault(bare_ch, coord)
            py = str(row.get("NAME_PY", "") or "").strip()
            if py:
                self._cnty[py] = coord             # "Yancheng Xian"
                self._cnty[py.lower()] = coord     # "yancheng xian"
                bare_py = _PY_SFX_CNTY.sub("", py).strip()
                if bare_py != py:
                    self._cnty.setdefault(bare_py, coord)        # "Yancheng"
                    self._cnty.setdefault(bare_py.lower(), coord) # "yancheng"

    # ── public ────────────────────────────────────────────────────────────────

    def lookup_province(self, name) -> tuple[float, float] | None:
        if not name or (isinstance(name, float) and pd.isna(name)):
            return None
        s = str(name).strip()
        return (self._prov.get(s)
                or self._prov.get(s.lower()))

    def lookup_prefecture(self, name) -> tuple[float, float] | None:
        if not name or (isinstance(name, float) and pd.isna(name)):
            return None
        s = str(name).strip()
        return (self._pref.get(s)
                or self._pref.get(s.lower())
                or self._pref.get(_SFXS_PREF.sub("", s))
                or self._pref.get(_PY_SFX_PREF.sub("", s).strip().lower()))

    def lookup_county(self, name) -> tuple[float, float] | None:
        if not name or (isinstance(name, float) and pd.isna(name)):
            return None
        s = str(name).strip()
        return (self._cnty.get(s)
                or self._cnty.get(s.lower())
                or self._cnty.get(_SFXS_CNTY.sub("", s))
                or self._cnty.get(_PY_SFX_CNTY.sub("", s).strip().lower()))

    def geocode_row(
        self,
        cnty_val=None,
        pref_val=None,
        prov_val=None,
    ) -> tuple[float | None, float | None, str | None]:
        """
        Return (lat, lon, matched_level) for the most specific available input.
        Any argument may be None or NaN.
        """
        for val, fn, level in (
            (cnty_val, self.lookup_county,     "county"),
            (pref_val, self.lookup_prefecture, "prefecture"),
            (prov_val, self.lookup_province,   "province"),
        ):
            coords = fn(val)
            if coords:
                return (*coords, level)
        return (None, None, None)

    def geocode_dataframe(
        self,
        df: pd.DataFrame,
        prov_col: str | None = None,
        pref_col: str | None = None,
        cnty_col: str | None = None,
    ) -> pd.DataFrame:
        """
        Add '_lat', '_lon', '_geo_level' columns to *df* (copy).
        Columns that are None are silently ignored.
        """
        out = df.copy()
        lats, lons, levels = [], [], []

        for _, row in df.iterrows():
            lat, lon, level = self.geocode_row(
                cnty_val=row[cnty_col] if cnty_col else None,
                pref_val=row[pref_col] if pref_col else None,
                prov_val=row[prov_col] if prov_col else None,
            )
            lats.append(lat)
            lons.append(lon)
            levels.append(level)

        out["_lat"]       = lats
        out["_lon"]       = lons
        out["_geo_level"] = levels
        return out
