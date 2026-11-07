"""
Active Input Data Exporter for Portfolio Optimization by Khim (v2.4 Institutional Edition).
Exports the exact live historical price series (with trading volume & daily returns)
and the active parameter matrices (E(R), Std_Dev, Correlation, Covariance) used in the user's
current optimization run.
Guaranteed 100% roundtrip-compatible with `engine.data_loader.parse_uploaded_file`.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _common_styles():
    navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    diag_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    title_font = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    sec_font = Font(name="Segoe UI", size=11, bold=True, color="0F172A")
    hdr_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    reg_font = Font(name="Segoe UI", size=10, color="1E293B")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    return {
        "navy_fill": navy_fill,
        "sub_fill": sub_fill,
        "zebra_fill": zebra_fill,
        "diag_fill": diag_fill,
        "title_font": title_font,
        "sec_font": sec_font,
        "hdr_font": hdr_font,
        "bold_font": bold_font,
        "reg_font": reg_font,
        "thin_border": thin_border,
    }


def export_live_price_dataset_xlsx(
    symbols: list[str],
    df_prices: pd.DataFrame,
    df_volumes: pd.DataFrame | None = None,
    daily_returns_df: pd.DataFrame | None = None,
    latest_prices: dict[str, float] | None = None,
    data_meta: dict[str, Any] | None = None,
) -> bytes:
    """
    Generate a 4-sheet Excel workbook containing the active portfolio's historical data:
    1. Historical_Prices (Date + Ticker Prices -> 100% Roundtrip Mode B compatible)
    2. Trading_Volume (Date + Ticker Daily Volumes)
    3. Daily_Returns (Date + Daily Percentage Returns R_i,t)
    4. Universe_Summary (Metadata, Date Window, Per-Ticker Price & Volume Summary)
    """
    st = _common_styles()
    wb = Workbook()
    meta = data_meta or {}
    latest_map = latest_prices or {}

    clean_syms = [str(s).strip().upper() for s in symbols if s in df_prices.columns]
    if not clean_syms:
        clean_syms = [str(c).strip().upper() for c in df_prices.columns]

    df_p = df_prices[clean_syms].copy()
    if daily_returns_df is None or len(daily_returns_df) == 0:
        df_r = df_p.pct_change().dropna(how="any")
    else:
        df_r = daily_returns_df[[s for s in clean_syms if s in daily_returns_df.columns]].copy()

    if df_volumes is not None and len(df_volumes) > 0:
        vol_cols = [s for s in clean_syms if s in df_volumes.columns]
        df_v = df_volumes[vol_cols].reindex(df_p.index).fillna(0.0)
    else:
        df_v = pd.DataFrame(0.0, index=df_p.index, columns=clean_syms)

    # =========================================================================
    # SHEET 1: Historical_Prices (Roundtrip Mode B Primary Sheet)
    # =========================================================================
    ws_p = wb.active
    ws_p.title = "Historical_Prices"
    ws_p.views.sheetView[0].showGridLines = True

    p_headers = ["Date"] + clean_syms
    for col_i, h in enumerate(p_headers, start=1):
        c = ws_p.cell(row=1, column=col_i, value=h)
        c.fill = st["navy_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_p.column_dimensions[get_column_letter(col_i)].width = 16

    for r_idx, (dt, row_vals) in enumerate(df_p.iterrows(), start=2):
        dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        c_dt = ws_p.cell(row=r_idx, column=1, value=dt_str)
        c_dt.font = st["reg_font"]
        c_dt.alignment = Alignment(horizontal="center")
        c_dt.border = st["thin_border"]

        for c_i, sym in enumerate(clean_syms, start=2):
            val = float(row_vals[sym])
            c_val = ws_p.cell(row=r_idx, column=c_i, value=val)
            c_val.number_format = "#,##0.00" if val % 1 != 0 else "#,##0"
            c_val.font = st["reg_font"]
            c_val.border = st["thin_border"]

    # =========================================================================
    # SHEET 2: Trading_Volume (Daily Trading Volume per Asset)
    # =========================================================================
    ws_v = wb.create_sheet(title="Trading_Volume")
    ws_v.views.sheetView[0].showGridLines = True

    v_headers = ["Date"] + clean_syms
    for col_i, h in enumerate(v_headers, start=1):
        c = ws_v.cell(row=1, column=col_i, value=h)
        c.fill = st["navy_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_v.column_dimensions[get_column_letter(col_i)].width = 18

    for r_idx, (dt, row_vals) in enumerate(df_v.iterrows(), start=2):
        dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        c_dt = ws_v.cell(row=r_idx, column=1, value=dt_str)
        c_dt.font = st["reg_font"]
        c_dt.alignment = Alignment(horizontal="center")
        c_dt.border = st["thin_border"]

        for c_i, sym in enumerate(clean_syms, start=2):
            v_val = float(row_vals[sym]) if sym in row_vals else 0.0
            c_val = ws_v.cell(row=r_idx, column=c_i, value=v_val)
            c_val.number_format = "#,##0"
            c_val.font = st["reg_font"]
            c_val.border = st["thin_border"]

    # =========================================================================
    # SHEET 3: Daily_Returns (Daily Simple Returns R_{i,t})
    # =========================================================================
    ws_r = wb.create_sheet(title="Daily_Returns")
    ws_r.views.sheetView[0].showGridLines = True

    r_headers = ["Date"] + clean_syms
    for col_i, h in enumerate(r_headers, start=1):
        c = ws_r.cell(row=1, column=col_i, value=h)
        c.fill = st["sub_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_r.column_dimensions[get_column_letter(col_i)].width = 16

    for r_idx, (dt, row_vals) in enumerate(df_r.iterrows(), start=2):
        dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        c_dt = ws_r.cell(row=r_idx, column=1, value=dt_str)
        c_dt.font = st["reg_font"]
        c_dt.alignment = Alignment(horizontal="center")
        c_dt.border = st["thin_border"]

        for c_i, sym in enumerate(clean_syms, start=2):
            ret_val = float(row_vals[sym]) if sym in row_vals else 0.0
            c_val = ws_r.cell(row=r_idx, column=c_i, value=ret_val)
            c_val.number_format = "0.00%"
            c_val.font = st["reg_font"]
            c_val.border = st["thin_border"]

    # =========================================================================
    # SHEET 4: Universe_Summary (Dataset Metadata & Per-Stock Statistics)
    # =========================================================================
    ws_s = wb.create_sheet(title="Universe_Summary")
    ws_s.views.sheetView[0].showGridLines = True

    ws_s.merge_cells("A1:H2")
    ws_s["A1"] = "TỔNG HỢP DỮ LIỆU GIÁ LỊCH SỬ & KHỐI LƯỢNG GIAO DỊCH ĐẦU VÀO (MVO INPUT DATASET)"
    for row in ws_s.iter_rows(min_row=1, max_row=2, min_col=1, max_col=8):
        for cell in row:
            cell.fill = st["navy_fill"]
            cell.font = st["title_font"]
            cell.alignment = Alignment(horizontal="center", vertical="center")

    from_dt = meta.get("from_date") or (
        df_p.index[0].strftime("%Y-%m-%d") if hasattr(df_p.index[0], "strftime") else str(df_p.index[0])[:10]
    )
    to_dt = meta.get("to_date") or (
        df_p.index[-1].strftime("%Y-%m-%d") if hasattr(df_p.index[-1], "strftime") else str(df_p.index[-1])[:10]
    )

    info_rows = [
        ("Ngày trích xuất", datetime.now().strftime("%Y-%m-%d %H:%M"), "Nguồn dữ liệu", meta.get("source", "HayInsights Live API")),
        ("Khung thời gian (Window)", str(meta.get("range", "1y")).upper(), "Phiên bản công thức giá", meta.get("formula_version", "vnsc-adjusted-close-v1")),
        ("Ngày bắt đầu", from_dt, "Ngày kết thúc", to_dt),
        ("Số lượng cổ phiếu", len(clean_syms), "Số phiên giao dịch (Aligned)", len(df_p)),
    ]
    for idx, (k1, v1, k2, v2) in enumerate(info_rows, start=4):
        ws_s.cell(row=idx, column=1, value=k1).font = st["bold_font"]
        ws_s.cell(row=idx, column=2, value=v1).font = st["reg_font"]
        ws_s.cell(row=idx, column=4, value=k2).font = st["bold_font"]
        ws_s.cell(row=idx, column=5, value=v2).font = st["reg_font"]
        for c_i in (1, 2, 4, 5):
            ws_s.cell(row=idx, column=c_i).border = st["thin_border"]

    ws_s["A10"] = "THỐNG KÊ CHI TIẾT TỪNG MÃ CỔ PHIẾU TRONG RỔ TỐI ƯU HÓA"
    ws_s["A10"].font = st["sec_font"]

    sum_headers = [
        "Mã CP",
        "Giá Khớp Lệnh Gần Nhất (VNĐ)",
        "Giá Điều Chỉnh Đầu Kỳ",
        "Giá Điều Chỉnh Cuối Kỳ",
        "Tăng Trưởng Lũy Kế (%)",
        "KLGD Trung Bình / Phiên",
        "KLGD Cao Nhất Phiên",
        "Tổng KLGD Toàn Kỳ",
    ]
    for col_i, h in enumerate(sum_headers, start=1):
        c = ws_s.cell(row=11, column=col_i, value=h)
        c.fill = st["sub_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_s.column_dimensions[get_column_letter(col_i)].width = 24

    for i, sym in enumerate(clean_syms):
        r = 12 + i
        p_series = df_p[sym].dropna()
        v_series = df_v[sym].dropna() if sym in df_v.columns else pd.Series([0.0])

        p_first = float(p_series.iloc[0]) if len(p_series) > 0 else 0.0
        p_last = float(p_series.iloc[-1]) if len(p_series) > 0 else 0.0
        p_raw_latest = float(latest_map.get(sym, p_last))
        cum_ret = (p_last / p_first - 1.0) if p_first > 0 else 0.0

        v_avg = float(v_series.mean()) if len(v_series) > 0 else 0.0
        v_max = float(v_series.max()) if len(v_series) > 0 else 0.0
        v_sum = float(v_series.sum()) if len(v_series) > 0 else 0.0

        ws_s.cell(row=r, column=1, value=sym).font = st["bold_font"]
        ws_s.cell(row=r, column=2, value=p_raw_latest).number_format = "#,##0"
        ws_s.cell(row=r, column=3, value=p_first).number_format = "#,##0.00"
        ws_s.cell(row=r, column=4, value=p_last).number_format = "#,##0.00"
        ws_s.cell(row=r, column=5, value=cum_ret).number_format = "0.00%"
        ws_s.cell(row=r, column=6, value=v_avg).number_format = "#,##0"
        ws_s.cell(row=r, column=7, value=v_max).number_format = "#,##0"
        ws_s.cell(row=r, column=8, value=v_sum).number_format = "#,##0"

        for col_i in range(1, 9):
            ws_s.cell(row=r, column=col_i).border = st["thin_border"]

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_live_parameter_matrix_xlsx(
    symbols: list[str],
    mu: list[float] | np.ndarray,
    std: list[float] | np.ndarray,
    corr: list[list[float]] | np.ndarray,
    cov: list[list[float]] | np.ndarray,
    latest_prices: dict[str, float] | None = None,
    rf: float = 0.045,
    data_meta: dict[str, Any] | None = None,
) -> bytes:
    """
    Generate a 3-sheet Excel workbook containing the active portfolio's parameter matrices:
    1. Parameters (Symbol, Expected_Return, Std_Dev, Latest_Price + Correlation Matrix -> Roundtrip Mode A compatible)
    2. Covariance_Matrix (Annualized Variance-Covariance Matrix Sigma)
    3. Asset_Statistics (Summary of moments, Sharpe ratios, and data provenance)
    """
    st = _common_styles()
    wb = Workbook()
    meta = data_meta or {}
    latest_map = latest_prices or {}

    clean_syms = [str(s).strip().upper() for s in symbols]
    n = len(clean_syms)
    mu_arr = np.asarray(mu, dtype=float)
    std_arr = np.asarray(std, dtype=float)
    corr_arr = np.asarray(corr, dtype=float)
    cov_arr = np.asarray(cov, dtype=float)

    # =========================================================================
    # SHEET 1: Parameters (100% Roundtrip Mode A Compatible)
    # =========================================================================
    ws_param = wb.active
    ws_param.title = "Parameters"
    ws_param.views.sheetView[0].showGridLines = True

    param_headers = ["Symbol", "Expected_Return", "Std_Dev", "Latest_Price"] + clean_syms
    for col_i, h in enumerate(param_headers, start=1):
        c = ws_param.cell(row=1, column=col_i, value=h)
        c.fill = st["navy_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_param.column_dimensions[get_column_letter(col_i)].width = 16 if col_i <= 4 else 13

    for i, sym in enumerate(clean_syms):
        r = 2 + i
        c_sym = ws_param.cell(row=r, column=1, value=sym)
        c_sym.font = st["bold_font"]
        c_sym.alignment = Alignment(horizontal="center")

        c_er = ws_param.cell(row=r, column=2, value=float(mu_arr[i]))
        c_er.number_format = "0.00%"
        c_er.font = st["reg_font"]

        c_std = ws_param.cell(row=r, column=3, value=float(std_arr[i]))
        c_std.number_format = "0.00%"
        c_std.font = st["reg_font"]

        c_lp = ws_param.cell(row=r, column=4, value=float(latest_map.get(sym, 50000.0)))
        c_lp.number_format = "#,##0"
        c_lp.font = st["reg_font"]

        for j in range(n):
            c_corr = ws_param.cell(row=r, column=5 + j, value=float(corr_arr[i, j]))
            c_corr.number_format = "0.0000"
            c_corr.font = st["bold_font"] if i == j else st["reg_font"]
            if i == j:
                c_corr.fill = st["diag_fill"]

        for col_i in range(1, 5 + n):
            ws_param.cell(row=r, column=col_i).border = st["thin_border"]

    # =========================================================================
    # SHEET 2: Covariance_Matrix (Annualized Sigma = Cov * 252)
    # =========================================================================
    ws_cov = wb.create_sheet(title="Covariance_Matrix")
    ws_cov.views.sheetView[0].showGridLines = True

    ws_cov["A1"] = "MA TRẬN HIỆP PHƯƠNG SAI NĂM HÓA (ANNUALIZED COVARIANCE MATRIX Σ - 252 TRADING DAYS)"
    ws_cov["A1"].font = st["sec_font"]

    ws_cov.cell(row=3, column=1, value="Mã CP").fill = st["sub_fill"]
    ws_cov.cell(row=3, column=1).font = st["hdr_font"]
    ws_cov.cell(row=3, column=1).border = st["thin_border"]

    for j, sym in enumerate(clean_syms):
        c = ws_cov.cell(row=3, column=2 + j, value=sym)
        c.fill = st["sub_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center")
        c.border = st["thin_border"]
        ws_cov.column_dimensions[get_column_letter(2 + j)].width = 15

    ws_cov.column_dimensions["A"].width = 16

    for i, sym in enumerate(clean_syms):
        r = 4 + i
        c_s = ws_cov.cell(row=r, column=1, value=sym)
        c_s.font = st["bold_font"]
        c_s.border = st["thin_border"]
        for j in range(n):
            c_v = ws_cov.cell(row=r, column=2 + j, value=float(cov_arr[i, j]))
            c_v.number_format = "0.000000"
            c_v.font = st["bold_font"] if i == j else st["reg_font"]
            c_v.border = st["thin_border"]
            if i == j:
                c_v.fill = st["diag_fill"]

    # =========================================================================
    # SHEET 3: Asset_Statistics (Summary of Individual Moments)
    # =========================================================================
    ws_stat = wb.create_sheet(title="Asset_Statistics")
    ws_stat.views.sheetView[0].showGridLines = True

    ws_stat["A1"] = "THỐNG KÊ THAM SỐ ĐẦU VÀO CỦA TỪNG TÀI SẢN (INDIVIDUAL ASSET MOMENTS)"
    ws_stat["A1"].font = st["sec_font"]

    ws_stat["A3"] = "Nguồn dữ liệu:"
    ws_stat["A3"].font = st["bold_font"]
    ws_stat["B3"] = meta.get("source", "HayInsights Live API")
    ws_stat["D3"] = "Lãi suất phi rủi ro (Rf):"
    ws_stat["D3"].font = st["bold_font"]
    ws_stat["E3"] = float(rf)
    ws_stat["E3"].number_format = "0.00%"

    stat_headers = [
        "Mã CP (Symbol)",
        "Lợi Suất Kỳ Vọng E(Ri) Năm",
        "Độ Lệch Chuẩn σi Năm",
        "Phương Sai σi² Năm",
        "Sharpe Ratio Đơn Lẻ",
        "Thị Giá Khớp Lệnh Gần Nhất (VNĐ)",
    ]
    for col_i, h in enumerate(stat_headers, start=1):
        c = ws_stat.cell(row=5, column=col_i, value=h)
        c.fill = st["navy_fill"]
        c.font = st["hdr_font"]
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = st["thin_border"]
        ws_stat.column_dimensions[get_column_letter(col_i)].width = 25

    for i, sym in enumerate(clean_syms):
        r = 6 + i
        er_i = float(mu_arr[i])
        sd_i = float(std_arr[i])
        var_i = float(cov_arr[i, i])
        sr_i = (er_i - rf) / sd_i if sd_i > 1e-8 else 0.0
        lp_i = float(latest_map.get(sym, 50000.0))

        ws_stat.cell(row=r, column=1, value=sym).font = st["bold_font"]
        ws_stat.cell(row=r, column=2, value=er_i).number_format = "0.00%"
        ws_stat.cell(row=r, column=3, value=sd_i).number_format = "0.00%"
        ws_stat.cell(row=r, column=4, value=var_i).number_format = "0.000000"
        ws_stat.cell(row=r, column=5, value=sr_i).number_format = "0.000"
        ws_stat.cell(row=r, column=6, value=lp_i).number_format = "#,##0"

        for col_i in range(1, 7):
            ws_stat.cell(row=r, column=col_i).border = st["thin_border"]

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
