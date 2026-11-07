"""
Data Loader & Parser for Textbook MVO Application.
Supports:
1. Built-in Vietnam Market Bluechip Dataset (252+ sessions, HOSE stocks)
2. Built-in Textbook Manual Parameters Preset (Bodie-Kane-Marcus style)
3. Excel (.xlsx) & CSV Upload Parser (both Historical Price Series and E(R)/Std/Correlation Matrix formats)
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from engine import textbook_math

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

STOCK_METADATA = {
    "FPT": {"name": "FPT Corp", "sector": "Công nghệ", "base_price": 114500.0, "mu": 0.24, "vol": 0.22},
    "MWG": {"name": "Thế Giới Di Động", "sector": "Bán lẻ", "base_price": 65200.0, "mu": 0.16, "vol": 0.29},
    "VCB": {"name": "Vietcombank", "sector": "Ngân hàng", "base_price": 91500.0, "mu": 0.13, "vol": 0.18},
    "TCB": {"name": "Techcombank", "sector": "Ngân hàng", "base_price": 24300.0, "mu": 0.18, "vol": 0.27},
    "HPG": {"name": "Tập đoàn Hòa Phát", "sector": "Thép & Vật liệu", "base_price": 27100.0, "mu": 0.17, "vol": 0.28},
    "SSI": {"name": "Chứng khoán SSI", "sector": "Chứng khoán", "base_price": 26800.0, "mu": 0.20, "vol": 0.33},
    "VNM": {"name": "Vinamilk", "sector": "Tiêu dùng", "base_price": 66400.0, "mu": 0.09, "vol": 0.16},
    "REE": {"name": "Cơ Điện Lạnh REE", "sector": "Năng lượng & Hạ tầng", "base_price": 64800.0, "mu": 0.15, "vol": 0.21},
    "GMD": {"name": "Gemadept", "sector": "Cảng & Logistics", "base_price": 78500.0, "mu": 0.21, "vol": 0.24},
    "GAS": {"name": "PV GAS", "sector": "Dầu khí & Tiện ích", "base_price": 71200.0, "mu": 0.10, "vol": 0.19},
}


def get_market_price_dataframe(symbols: list[str] | None = None, n_sessions: int = 252) -> pd.DataFrame:
    """
    Generate or load calibrated 252-session daily closing prices for selected HOSE stocks.
    Uses deterministic seed and realistic cross-asset factor correlations.
    """
    syms = [s.strip().upper() for s in (symbols or ["FPT", "MWG", "VCB", "HPG", "SSI"])]
    syms = [s for s in syms if s in STOCK_METADATA]
    if len(syms) < 2:
        syms = ["FPT", "MWG", "VCB", "HPG"]

    all_syms = list(STOCK_METADATA.keys())
    k = len(all_syms)
    rng = np.random.default_rng(20260252)

    dates = pd.bdate_range(end="2026-10-30", periods=n_sessions + 1)

    # Construct realistic market + sector correlation structure
    market_factor = rng.normal(0.0003, 0.010, size=n_sessions)
    fin_factor = rng.normal(0.0001, 0.008, size=n_sessions)

    price_dict: dict[str, list[float]] = {}
    for sym in all_syms:
        meta = STOCK_METADATA[sym]
        daily_mu = meta["mu"] / 252.0
        daily_vol = meta["vol"] / np.sqrt(252.0)

        beta_m = 0.85 if meta["sector"] not in ["Ngân hàng", "Chứng khoán"] else 1.15
        beta_fin = 0.75 if meta["sector"] in ["Ngân hàng", "Chứng khoán"] else 0.10

        idio_vol = max(0.005, np.sqrt(max(daily_vol**2 - (beta_m * 0.010) ** 2, 0.00004)))
        idio = rng.normal(0.0, idio_vol, size=n_sessions)

        raw_rets = daily_mu + beta_m * (market_factor - np.mean(market_factor)) + beta_fin * fin_factor + idio
        # Center sample mean/vol softly around calibrated realistic values
        raw_rets = (raw_rets - np.mean(raw_rets)) * (daily_vol / np.std(raw_rets, ddof=1)) + daily_mu

        p0 = meta["base_price"] / float(np.prod(1.0 + raw_rets))
        prices = [p0]
        for r in raw_rets:
            prices.append(round(prices[-1] * (1.0 + float(r)), 2))
        price_dict[sym] = prices

    # Override MWG with real CSV data if available and matching length
    mwg_csv = WORKSPACE_ROOT / "MWG_5y_daily_2021-11-02_2026-11-02.csv"
    if mwg_csv.exists() and "MWG" in syms:
        try:
            df_mwg = pd.read_csv(mwg_csv)
            if "close_vnd" in df_mwg.columns and len(df_mwg) >= n_sessions + 1:
                price_dict["MWG"] = df_mwg["close_vnd"].iloc[-(n_sessions + 1) :].astype(float).tolist()
        except Exception:
            pass

    df = pd.DataFrame({s: price_dict[s] for s in syms}, index=dates)
    df.index.name = "Date"
    return df


def parse_uploaded_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """
    Parse an uploaded .xlsx or .csv file in either:
    - Mode A: Parameter Matrix (Columns: Symbol, Expected_Return, Std_Dev, + Correlation Matrix)
    - Mode B: Historical Closing Prices (Column 0: Date, Columns 1..N: Stock Prices)
    """
    fname = filename.lower()
    if fname.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif fname.endswith(".xlsx") or fname.endswith(".xls"):
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        # Prefer sheet named 'Parameters', 'Prices', or first sheet
        sheet_to_read = xls.sheet_names[0]
        for sname in xls.sheet_names:
            if sname.lower() in ["parameters", "manual_params", "prices", "historical_prices"]:
                sheet_to_read = sname
                break
        df = pd.read_excel(xls, sheet_name=sheet_to_read)
    else:
        raise ValueError("Định dạng file không hỗ trợ. Vui lòng tải lên file .xlsx hoặc .csv.")

    df = df.dropna(how="all")
    cols_lower = [str(c).strip().lower() for c in df.columns]

    # Detect Mode A: Manual Parameters Table
    if "symbol" in cols_lower and ("expected_return" in cols_lower or "e(r)" in cols_lower):
        sym_col = df.columns[cols_lower.index("symbol")]
        er_col = df.columns[cols_lower.index("expected_return") if "expected_return" in cols_lower else cols_lower.index("e(r)")]
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

        er_raw = df_sub[er_col].astype(float).to_numpy()
        std_raw = df_sub[std_col].astype(float).to_numpy()

        # If user entered percentages like 18.5 instead of 0.185, convert automatically
        if np.max(np.abs(er_raw)) > 1.5 or np.max(std_raw) > 1.5:
            er_raw = er_raw / 100.0
            std_raw = std_raw / 100.0

        # Extract correlation columns matching symbols
        corr_mat = np.eye(n, dtype=float)
        col_map = {str(c).strip().upper(): c for c in df.columns}
        if all(s in col_map for s in symbols):
            corr_df = df_sub[[col_map[s] for s in symbols]].astype(float)
            corr_mat = corr_df.to_numpy()

        moments = textbook_math.build_moments_from_manual(
            symbols=symbols,
            expected_returns=er_raw.tolist(),
            std_devs=std_raw.tolist(),
            corr_matrix=corr_mat.tolist(),
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
        raise ValueError("File dữ liệu giá cần ít nhất 2 cột mã cổ phiếu hợp lệ.")

    df_clean = df_prices[numeric_cols].dropna(how="any")
    df_clean.columns = [str(c).strip().upper() for c in df_clean.columns]

    moments = textbook_math.compute_moments_from_prices(df_clean, trading_days=252)
    moments["source_type"] = "uploaded_prices"
    return moments
