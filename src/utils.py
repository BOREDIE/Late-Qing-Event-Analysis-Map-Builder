"""
utils.py
--------
Data loading and interactive column-selection helpers.
"""

import os
import sys
import pandas as pd

# ── loaders ───────────────────────────────────────────────────────────────────

def load_events(path: str) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif ext == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    else:
        raise ValueError(f"Unsupported file type: {ext!r}  (use .xlsx / .csv)")


# ── column-selection helpers ──────────────────────────────────────────────────

def _show_columns(df: pd.DataFrame):
    print("\nAvailable columns:")
    for i, col in enumerate(df.columns):
        sample = df[col].dropna().iloc[0] if df[col].notna().any() else "—"
        sample_str = str(sample)[:40]
        print(f"  [{i:2d}] {col:<35}  e.g. {sample_str}")


def _pick_col(df: pd.DataFrame, prompt: str) -> str | None:
    """Ask the user to choose one column by index or name. Empty → None."""
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return None
        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(df.columns):
                return df.columns[idx]
            print(f"  ✗ Index {idx} out of range (0–{len(df.columns)-1})")
        elif raw in df.columns:
            return raw
        else:
            print(f"  ✗ '{raw}' not found. Enter a column index or exact name.")


def _pick_cols(df: pd.DataFrame, prompt: str) -> list[str]:
    """Ask the user to choose multiple columns (comma-separated indices/names)."""
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return list(df.columns)
        cols = []
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                idx = int(token)
                if 0 <= idx < len(df.columns):
                    cols.append(df.columns[idx])
                else:
                    print(f"  ✗ Index {idx} out of range"); valid = False; break
            elif token in df.columns:
                cols.append(token)
            else:
                print(f"  ✗ Column '{token}' not found"); valid = False; break
        if valid:
            return cols


def prompt_column_mapping(df: pd.DataFrame) -> dict:
    """
    Interactive prompt that asks the user to identify geographic columns and
    popup display columns.

    Returns
    -------
    dict with keys:
        prov_col, pref_col, cnty_col  (str | None)
        popup_cols                    (list[str])
        color_col                     (str | None)
    """
    _show_columns(df)
    print()
    print("─" * 60)
    print("Geographic column mapping  (press Enter to skip any level)")
    print("─" * 60)

    prov_col  = _pick_col(df, "  Province-level column  : ")
    pref_col  = _pick_col(df, "  Prefecture-level column : ")
    cnty_col  = _pick_col(df, "  County-level column     : ")

    print()
    print("─" * 60)
    print("Display options")
    print("─" * 60)

    geo_cols = {c for c in (prov_col, pref_col, cnty_col) if c}
    default_popup = [c for c in df.columns if c not in geo_cols]
    popup_cols = _pick_cols(
        df,
        f"  Popup columns (indices/names, comma-sep; Enter = all {len(default_popup)} non-geo cols): ",
    ) or default_popup

    color_col = _pick_col(df, "  Color-code dots by column (Enter to skip)         : ")

    return dict(
        prov_col=prov_col,
        pref_col=pref_col,
        cnty_col=cnty_col,
        popup_cols=popup_cols,
        color_col=color_col,
    )


# ── auto-detect helper ────────────────────────────────────────────────────────

# Pass 1 — English / Pinyin column-name patterns (substring match on lowercased name).
# Columns whose names end with _ch or _py are sorted first so "prov_ch" is
# preferred over the bare "prov" (Pinyin-only) column when both exist.
# Expected naming convention: prov / prov_ch, pref / pref_ch, cnty / cnty_ch.
_PROV_EN = {"prov", "province"}
_PREF_EN = {"pref", "prefecture"}
_CNTY_EN = {"county", "cnty"}

# Pass 2 — Chinese column-name patterns (fallback).
# Stricter than Pass 1: the column name must equal or END with the character,
# so "省份/地区" does not match "省" but a column literally named "省" or "1省" would.
_PROV_ZH = {"省"}
_PREF_ZH = {"府", "州"}
_CNTY_ZH = {"县"}


def infer_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """
    Auto-detect geographic columns from column names.

    Pass 1 uses English / Pinyin patterns; columns suffixed with _ch or _py
    (Chinese / Pinyin content) are preferred over bare names so "prov_ch" wins
    over "prov" when both exist.

    Pass 2 falls back to Chinese character patterns only when no English match
    was found, using strict end-of-name matching to avoid false positives on
    descriptive columns like "省份/地区".

    Returns dict with keys prov_col, pref_col, cnty_col (each str or None).
    """
    result: dict[str, str | None] = {
        "prov_col": None, "pref_col": None, "cnty_col": None,
    }

    # Sort: _ch / _py / _en suffixed columns come before unsuffixed ones.
    ranked = sorted(
        df.columns,
        key=lambda c: (0 if c.lower().endswith(("_ch", "_py", "_en")) else 1),
    )

    for col in ranked:
        lo = col.lower()
        if result["prov_col"] is None and any(h in lo for h in _PROV_EN):
            result["prov_col"] = col
        elif result["pref_col"] is None and any(h in lo for h in _PREF_EN):
            result["pref_col"] = col
        elif result["cnty_col"] is None and any(h in lo for h in _CNTY_EN):
            result["cnty_col"] = col

    # Pass 2: Chinese column names — only if column ends with a geo character.
    for col in df.columns:
        for key, hints in [
            ("prov_col", _PROV_ZH),
            ("pref_col", _PREF_ZH),
            ("cnty_col", _CNTY_ZH),
        ]:
            if result[key] is None and any(col == h or col.endswith(h) for h in hints):
                result[key] = col
                break

    return result
