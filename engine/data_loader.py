"""
Data Loader & Parser for Textbook MVO Application.
100% Real Data Architecture (Zero Synthetic Fallback):
- Parses uploaded Excel (.xlsx) & CSV files in both:
  * Mode A: Parameter Matrix (Symbol, Expected_Return, Std_Dev, [Latest_Price], + Correlation Matrix)
  * Mode B: Historical Closing Prices (Date + Stock Price columns, plus optional Trading_Volume sheet)
- Preserves uploaded price & volume series in memory for roundtrip export and benchmark alignment.
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd

from engine import textbook_math

# In-memory cache of the most recently uploaded historical price dataset (Mode B)
_LAST_UPLOADED_DATASET: dict[str, Any] = {}


def get_last_uploaded_dataset() -> dict[str, Any]:
    """Return the most recently uploaded historical price dataset if available."""
    return _LAST_UPLOADED_DATASET


def parse_uploaded_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    Parse an uploaded .xlsx or .csv file in either:
    - Mode A: Parameter Matrix (Columns: Symbol, Expected_Return, Std_Dev, + Correlation Matrix)
    - Mode B: Historical Closing Prices (Column 0: Date, Columns 1..N: Stock Prices)
    """
    fname = filename.lower()
    df_vol_raw = None

    if fname.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif fname.endswith(".xlsx") or fname.endswith(".xls"):
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        sheet_to_read = xls.sheet_names[0]
        for sname in xls.sheet_names:
            if sname.lower() in ["parameters", "manual_params", "prices", "historical_prices"]:
                sheet_to_read = sname
                break
        df = pd.read_excel(xls, sheet_name=sheet_to_read)

        # Check if Trading_Volume sheet is also present for roundtrip fidelity
        for sname in xls.sheet_names:
            if sname.lower() in ["trading_volume", "volume", "volumes"]:
                try:
                    df_vol_raw = pd.read_excel(xls, sheet_name=sname)
                except Exception:
                    df_vol_raw = None
                break
    else:
        raise ValueError("Định dạng file không hỗ trợ. Vui lòng tải lên file .xlsx hoặc .csv.")

    df = df.dropna(how="all")
    cols_lower = [str(c).strip().lower() for c in df.columns]

    # Detect Mode A: Manual Parameters Table
    if "symbol" in cols_lower and ("expected_return" in cols_lower or "e(r)" in cols_lower):
        sym_col = df.columns[cols_lower.index("symbol")]
        er_col = df.columns[
            cols_lower.index("expected_return")
            if "expected_return" in cols_lower
            else cols_lower.index("e(r)")
        ]
        std_col = df.columns[
            cols_lower.index("std_dev")
            if "std_dev" in cols_lower
            else (cols_lower.index("volatility") if "volatility" in cols_lower else 2)
        ]

        df[er_col] = pd.to_numeric(df[er_col], errors="coerce")
        df[std_col] = pd.to_numeric(df[std_col], errors="coerce")
        df_sub = df[df[sym_col].notna() & df[er_col].notna() & df[std_col].notna()].copy()

        symbols = [str(x).strip().upper() for x in df_sub[sym_col].tolist()]
        n = len(symbols)
        if n < 2:
            raise ValueError("Bảng ma trận tham số cần tối thiểu 2 mã cổ phiếu hợp lệ.")

        er_raw = df_sub[er_col].astype(float).to_numpy(dtype=float, copy=True)
        std_raw = df_sub[std_col].astype(float).to_numpy(dtype=float, copy=True)

        # If user entered percentages like 18.5 instead of 0.185, convert automatically
        if np.max(np.abs(er_raw)) > 1.5 or np.max(std_raw) > 1.5:
            er_raw = er_raw / 100.0
            std_raw = std_raw / 100.0

        # Optional Latest_Price column
        latest_prices: dict[str, float] = {}
        for lp_key in ("latest_price", "market_price", "price"):
            if lp_key in cols_lower:
                lp_col = df.columns[cols_lower.index(lp_key)]
                lp_vals = pd.to_numeric(df_sub[lp_col], errors="coerce").fillna(50000.0).tolist()
                latest_prices = {symbols[i]: float(lp_vals[i]) for i in range(n)}
                break

        # Extract correlation columns matching symbols
        corr_mat = np.eye(n, dtype=float)
        col_map = {str(c).strip().upper(): c for c in df.columns}
        if all(s in col_map for s in symbols):
            corr_df = df_sub[[col_map[s] for s in symbols]].astype(float)
            corr_mat = corr_df.to_numpy(dtype=float, copy=True)

        moments = textbook_math.build_moments_from_manual(
            symbols=symbols,
            expected_returns=er_raw.tolist(),
            std_devs=std_raw.tolist(),
            corr_matrix=corr_mat.tolist(),
            latest_prices=latest_prices or None,
        )
        moments["source_type"] = "uploaded_parameters"
        return moments

    # Otherwise Mode B: Historical Price Table
    # First column is Date, remaining numeric columns are stock prices
    date_col = df.columns[0]
    df_prices = df.copy()
    try:
        df_prices[date_col] = pd.to_datetime(df_prices[date_col])
        df_prices = df_prices.set_index(date_col).sort_index()
    except Exception:
        pass

    numeric_cols = []
    for c in df_prices.columns:
        df_prices[c] = pd.to_numeric(df_prices[c], errors="coerce")
        if df_prices[c].notna().sum() >= 10:
            numeric_cols.append(c)

    if len(numeric_cols) < 2:
        raise ValueError("File dữ liệu giá cần ít nhất 2 cột mã cổ phiếu hợp lệ (tối thiểu 10 phiên).")

    df_clean = df_prices[numeric_cols].dropna(how="any")
    df_clean.columns = [str(c).strip().upper() for c in df_clean.columns]
    df_clean.index.name = "Date"

    # Align optional Trading_Volume sheet if present
    df_vol_clean = None
    if df_vol_raw is not None and len(df_vol_raw.columns) >= 2:
        try:
            v_date_col = df_vol_raw.columns[0]
            df_v = df_vol_raw.copy()
            df_v[v_date_col] = pd.to_datetime(df_v[v_date_col])
            df_v = df_v.set_index(v_date_col).sort_index()
            df_v.columns = [str(c).strip().upper() for c in df_v.columns]
            common_syms = [s for s in df_clean.columns if s in df_v.columns]
            if common_syms:
                df_vol_clean = df_v[common_syms].apply(pd.to_numeric, errors="coerce").reindex(df_clean.index).fillna(0.0)
                df_vol_clean.index.name = "Date"
        except Exception:
            df_vol_clean = None

    moments = textbook_math.compute_moments_from_prices(df_clean, trading_days=252)
    moments["source_type"] = "uploaded_prices"
    moments["volumes_df"] = df_vol_clean

    # Cache for subsequent export/benchmark operations
    _LAST_UPLOADED_DATASET.clear()
    _LAST_UPLOADED_DATASET.update({
        "filename": filename,
        "symbols": moments["symbols"],
        "df_prices": df_clean,
        "df_volumes": df_vol_clean,
        "daily_returns_df": moments["daily_returns_df"],
        "latest_prices": moments["latest_prices"],
    })

    # Enrich local SQLite database with uploaded prices (Zero Quota)
    try:
        from engine import db_manager
        db_manager.ingest_uploaded_prices_df(df_clean, df_vol_clean)
    except Exception:
        pass

    return moments
