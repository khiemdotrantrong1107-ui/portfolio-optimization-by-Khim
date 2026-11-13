"""
Data Loader & Parser for Textbook MVO Application.
100% Real Data Architecture (Zero Synthetic Fallback):
- Parses uploaded Excel (.xlsx) & CSV files in both:
  * Mode A: Parameter Matrix (Symbol, Expected_Return, Std_Dev, [Latest_Price], + Correlation Matrix)
  * Mode B: Historical Closing Prices (Date + Stock Price columns, plus optional Trading_Volume sheet)
- Preserves uploaded price & volume series in memory for roundtrip export and benchmark alignment.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import io
from typing import Any
import uuid

import numpy as np
import pandas as pd

from engine import textbook_math

# Bounded LRU cache of uploaded historical price datasets keyed by dataset_id (Mode B).
# Never implicitly read by manual_matrix mode.
MAX_UPLOADED_DATASETS = 20
_UPLOADED_DATASETS: OrderedDict[str, dict[str, Any]] = OrderedDict()


def get_uploaded_dataset(dataset_id: str | None) -> dict[str, Any] | None:
    """Return an uploaded historical price dataset strictly by explicit dataset_id."""
    if not dataset_id:
        return None
    ds = _UPLOADED_DATASETS.get(dataset_id)
    if ds is not None:
        _UPLOADED_DATASETS.move_to_end(dataset_id)
    return ds


def clear_uploaded_datasets() -> None:
    """Clear uploaded dataset cache (primarily for deterministic testing)."""
    _UPLOADED_DATASETS.clear()


def _detect_duplicates(items: list[str]) -> list[str]:
    seen: set[str] = set()
    dups: list[str] = []
    for item in items:
        if item in seen and item not in dups:
            dups.append(item)
        seen.add(item)
    return dups


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
    if df.empty:
        raise ValueError("File tải lên không có dữ liệu.")
    cols_lower = [str(c).strip().lower() for c in df.columns]
    uploaded_at = datetime.now().isoformat(timespec="seconds")

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

        df_sub = df[df[sym_col].notna()].copy()
        df_sub[sym_col] = df_sub[sym_col].astype(str).str.strip().str.upper()
        df_sub = df_sub[df_sub[sym_col] != ""]

        symbols = df_sub[sym_col].tolist()
        dups = _detect_duplicates(symbols)
        if dups:
            raise ValueError(f"File ma trận tham số chứa mã cổ phiếu bị trùng: {', '.join(dups)}.")

        n = len(symbols)
        if n < 2:
            raise ValueError("Bảng ma trận tham số cần tối thiểu 2 mã cổ phiếu hợp lệ.")

        er_num = pd.to_numeric(df_sub[er_col], errors="coerce").to_numpy(dtype=float, copy=True)
        std_num = pd.to_numeric(df_sub[std_col], errors="coerce").to_numpy(dtype=float, copy=True)

        if not np.all(np.isfinite(er_num)) or not np.all(np.isfinite(std_num)):
            raise ValueError("File ma trận tham số chứa giá trị Expected_Return hoặc Std_Dev bị thiếu, NaN hoặc Inf.")
        if np.any(std_num <= 0):
            raise ValueError("Độ lệch chuẩn (Std_Dev) của mọi mã cổ phiếu phải > 0.")

        # If user entered percentages like 18.5 instead of 0.185, convert automatically
        if np.max(np.abs(er_num)) > 1.5 or np.max(std_num) > 1.5:
            er_num = er_num / 100.0
            std_num = std_num / 100.0

        # Optional Latest_Price column (NEVER inject synthetic 50,000.0 fallback)
        latest_prices: dict[str, float | None] = {sym: None for sym in symbols}
        has_any_price = False
        for lp_key in ("latest_price", "market_price", "price"):
            if lp_key in cols_lower:
                lp_col = df.columns[cols_lower.index(lp_key)]
                raw_lp = df_sub[lp_col].tolist()
                parsed_lp = pd.to_numeric(df_sub[lp_col], errors="coerce").to_numpy(dtype=float, copy=True)
                for i, sym in enumerate(symbols):
                    raw_cell = raw_lp[i]
                    val = parsed_lp[i]
                    if raw_cell is None or (isinstance(raw_cell, float) and np.isnan(raw_cell)) or str(raw_cell).strip() == "":
                        latest_prices[sym] = None
                    elif not np.isfinite(val) or val <= 0:
                        raise ValueError(f"Giá hiện tại (Latest_Price) của mã '{sym}' phải là số hữu hạn > 0.")
                    else:
                        latest_prices[sym] = float(val)
                        has_any_price = True
                break

        # Extract correlation columns matching symbols
        corr_mat = np.eye(n, dtype=float)
        col_map: dict[str, Any] = {}
        for col in df.columns:
            c_up = str(col).strip().upper()
            if c_up in col_map and c_up in symbols:
                raise ValueError(f"File ma trận tham số có cột tương quan bị trùng tên mã '{c_up}'.")
            col_map[c_up] = col

        if all(s in col_map for s in symbols):
            corr_df = df_sub[[col_map[s] for s in symbols]].apply(pd.to_numeric, errors="coerce")
            corr_mat = corr_df.to_numpy(dtype=float, copy=True)
            if not np.all(np.isfinite(corr_mat)):
                raise ValueError("Ma trận tương quan chứa ô trống, chữ hoặc NaN/Inf.")

        moments = textbook_math.build_moments_from_manual(
            symbols=symbols,
            expected_returns=er_num.tolist(),
            std_devs=std_num.tolist(),
            corr_matrix=corr_mat.tolist(),
            latest_prices=latest_prices if has_any_price else None,
        )
        moments["source_type"] = "uploaded_parameters"
        moments["filename"] = filename
        moments["uploaded_at"] = uploaded_at
        moments["dataset_id"] = None
        return moments

    # Otherwise Mode B: Historical Price Table
    # First column is Date, remaining numeric columns are stock prices
    date_col = df.columns[0]
    df_prices = df.copy()
    parsed_dates = pd.to_datetime(df_prices[date_col], errors="coerce")
    if parsed_dates.isna().all():
        raise ValueError("Cột đầu tiên của file giá lịch sử phải là ngày hợp lệ (Date).")
    if parsed_dates.isna().any():
        bad_rows = int(parsed_dates.isna().sum())
        raise ValueError(f"File giá lịch sử có {bad_rows} dòng không đọc được ngày giao dịch hợp lệ.")
    df_prices[date_col] = parsed_dates
    df_prices = df_prices.set_index(date_col).sort_index()
    if df_prices.index.has_duplicates:
        df_prices = df_prices[~df_prices.index.duplicated(keep="last")]

    raw_col_names = [str(c).strip().upper() for c in df_prices.columns]
    dup_cols = _detect_duplicates([c for c in raw_col_names if c])
    if dup_cols:
        raise ValueError(f"File giá lịch sử có cột mã cổ phiếu bị trùng: {', '.join(dup_cols)}.")

    numeric_cols = []
    for c in df_prices.columns:
        df_prices[c] = pd.to_numeric(df_prices[c], errors="coerce")
        col_arr = df_prices[c].to_numpy(dtype=float, copy=True)
        if np.any(np.isinf(col_arr)):
            raise ValueError(f"Cột mã '{c}' chứa giá trị Inf không hợp lệ.")
        valid_vals = col_arr[np.isfinite(col_arr)]
        if len(valid_vals) > 0 and np.any(valid_vals <= 0):
            raise ValueError(f"Cột mã '{c}' chứa giá <= 0; vui lòng kiểm tra lại dữ liệu giá.")
        if df_prices[c].notna().sum() >= 10:
            numeric_cols.append(c)

    if len(numeric_cols) < 2:
        raise ValueError("File dữ liệu giá cần ít nhất 2 cột mã cổ phiếu hợp lệ (tối thiểu 10 phiên).")

    total_rows_before_align = len(df_prices)
    df_clean = df_prices[numeric_cols].dropna(how="any")
    dropped_days_count = max(0, int(total_rows_before_align - len(df_clean)))
    if len(df_clean) < 10:
        raise ValueError(
            f"Sau khi căn chỉnh ngày trùng khớp giữa các mã chỉ còn {len(df_clean)} phiên (cần tối thiểu 10 phiên)."
        )

    df_clean.columns = [str(c).strip().upper() for c in df_clean.columns]
    df_clean.index.name = "Date"

    # Align optional Trading_Volume sheet if present
    df_vol_clean = None
    if df_vol_raw is not None and len(df_vol_raw.columns) >= 2:
        try:
            v_date_col = df_vol_raw.columns[0]
            df_v = df_vol_raw.copy()
            df_v[v_date_col] = pd.to_datetime(df_v[v_date_col], errors="coerce")
            df_v = df_v.dropna(subset=[v_date_col]).set_index(v_date_col).sort_index()
            df_v = df_v[~df_v.index.duplicated(keep="last")]
            df_v.columns = [str(c).strip().upper() for c in df_v.columns]
            common_syms = [s for s in df_clean.columns if s in df_v.columns]
            if common_syms:
                df_vol_clean = df_v[common_syms].apply(pd.to_numeric, errors="coerce").reindex(df_clean.index).fillna(0.0)
                df_vol_clean.index.name = "Date"
        except Exception:
            df_vol_clean = None

    moments = textbook_math.compute_moments_from_prices(df_clean, trading_days=252)
    from_date = str(df_clean.index[0].date())
    to_date = str(df_clean.index[-1].date())
    dataset_id = f"upl_{uuid.uuid4().hex[:12]}"
    latest_price_dates = {sym: to_date for sym in moments["symbols"]}

    moments["source_type"] = "uploaded_prices"
    moments["dataset_id"] = dataset_id
    moments["filename"] = filename
    moments["uploaded_at"] = uploaded_at
    moments["from_date"] = from_date
    moments["to_date"] = to_date
    moments["dropped_days_count"] = dropped_days_count
    moments["aligned_price_sessions"] = int(len(df_clean))
    moments["aligned_sessions"] = int(len(df_clean) - 1)
    moments["latest_price_dates"] = latest_price_dates
    moments["volumes_df"] = df_vol_clean

    # Store strictly under bounded LRU keyed by dataset_id
    _UPLOADED_DATASETS[dataset_id] = {
        "dataset_id": dataset_id,
        "filename": filename,
        "uploaded_at": uploaded_at,
        "from_date": from_date,
        "to_date": to_date,
        "dropped_days_count": dropped_days_count,
        "aligned_price_sessions": int(len(df_clean)),
        "aligned_sessions": int(len(df_clean) - 1),
        "latest_price_dates": latest_price_dates,
        "symbols": moments["symbols"],
        "df_prices": df_clean,
        "df_volumes": df_vol_clean,
        "daily_returns_df": moments["daily_returns_df"],
        "latest_prices": moments["latest_prices"],
    }
    _UPLOADED_DATASETS.move_to_end(dataset_id)
    while len(_UPLOADED_DATASETS) > MAX_UPLOADED_DATASETS:
        _UPLOADED_DATASETS.popitem(last=False)

    return moments
