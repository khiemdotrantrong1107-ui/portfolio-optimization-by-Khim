"""
Institutional Portfolio Management Excel Exporter (A-Z Calculations).
Generates a 6-sheet professional .xlsx workbook:
1. 01_Executive_Summary
2. 02_Asset_Statistics
3. 03_Covariance_Correlation
4. 04_Matrix_Calculations (Merton scalars A, B, C, D, Sigma^-1, live Excel formulas)
5. 05_Efficient_Frontier_Data (with embedded Scatter Chart)
6. 06_Execution_Order_Sheet (HOSE Lot-100 Share Allocation & Costs)
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import numpy as np
from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def export_mvo_institutional_workbook(
    analysis_data: dict[str, Any],
    lang: str | None = None,
    risk_report_basis: str | None = None,
) -> bytes:
    """Build the complete 8-sheet MVO Excel workbook strictly synchronized with the active analysis snapshot."""
    wb = Workbook()
    lang_code = "en" if str(lang or analysis_data.get("lang") or "vi").lower() == "en" else "vi"
    basis_key = str(risk_report_basis or analysis_data.get("risk_report_basis") or "target_complete").lower()

    # Palette & Typography
    navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    accent_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    warn_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    title_font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    sec_font = Font(name="Segoe UI", size=11, bold=True, color="0F172A")
    tbl_hdr_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    reg_font = Font(name="Segoe UI", size=10, color="1E293B")
    warn_font = Font(name="Segoe UI", size=10, bold=True, color="92400E")
    formula_font = Font(name="Consolas", size=9, color="047857")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    symbols: list[str] = analysis_data["symbols"]
    n = len(symbols)
    mu: list[float] = analysis_data["mu"]
    cagr: list[float] | None = analysis_data.get("cagr")
    std: list[float] = analysis_data["std"]
    cov: list[list[float]] = analysis_data["cov"]
    corr: list[list[float]] = analysis_data["corr"]
    inv_cov: list[list[float]] | None = analysis_data.get("inv_cov")
    scalars: dict[str, float] | None = analysis_data.get("merton_scalars")
    merton_status: str = analysis_data.get("merton_status", "available" if inv_cov is not None else "singular_covariance")
    rf: float = analysis_data["rf"]
    gamma: float = analysis_data.get("risk_aversion_gamma", analysis_data["risk_aversion_A"])
    nav_vnd: float = float(analysis_data.get("nav_vnd", 1_000_000_000.0))
    allow_short: bool = bool(analysis_data.get("allow_short", False))
    latest_prices: dict[str, float | None] = analysis_data.get("latest_prices", {}) or {}
    data_meta: dict[str, Any] = analysis_data.get("data_meta", {}) or {}
    execution: dict[str, Any] = analysis_data.get("execution", {}) or {}
    run_id: str = str(analysis_data.get("run_id", "N/A"))
    computed_at: str = str(analysis_data.get("computed_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    gmv = analysis_data["gmv"]
    tan = analysis_data["tangency"]
    comp = analysis_data["complete_portfolio"]
    eq = analysis_data["equal_weight"]
    tan_status = comp.get("tangency_status", "optimal")
    exec_ready = execution.get("status") == "ready"
    exec_w_post = execution.get("actual_weights_post_fee", [0.0] * n)
    exec_cash_post = float(execution.get("actual_cash_weight_post_fee", 1.0))

    # Derive Executed Post-Fee Portfolio summary stats cleanly
    if exec_ready:
        w_eq_exec = np.asarray(execution.get("actual_equity_weights_within_basket", [0.0] * n), dtype=float)
        y_exec = max(0.0, 1.0 - exec_cash_post)
        mu_np = np.asarray(mu, dtype=float)
        cov_np = np.asarray(cov, dtype=float)
        if y_exec > 1e-9:
            ex_ret_basket = float(np.dot(w_eq_exec, mu_np))
            ex_var_basket = max(0.0, float(w_eq_exec.T @ cov_np @ w_eq_exec))
            exec_ret = rf + y_exec * (ex_ret_basket - rf)
            exec_vol = y_exec * float(np.sqrt(ex_var_basket))
            exec_var = exec_vol**2
            exec_sr = (exec_ret - rf) / exec_vol if exec_vol > 1e-8 else 0.0
        else:
            exec_ret, exec_vol, exec_var, exec_sr = rf, 0.0, 0.0, 0.0
    else:
        y_exec = None
        exec_ret = exec_vol = exec_var = exec_sr = None

    def _tr(vi: str, en: str) -> str:
        return en if lang_code == "en" else vi

    def _style_range(ws, min_col, min_row, max_col, max_row, font=None, fill=None, border=None, num_format=None, align=None):
        for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row:
                if font:
                    cell.font = font
                if fill:
                    cell.fill = fill
                if border:
                    cell.border = border
                if num_format:
                    cell.number_format = num_format
                if align:
                    cell.alignment = align

    # =========================================================================
    # SHEET 1: 01_Executive_Summary
    # Note: keep start_alloc_row=20 so tot_row for n=5 remains row 26 (D26=SUM)
    # =========================================================================
    ws1 = wb.active
    ws1.title = "01_Executive_Summary"
    ws1.views.sheetView[0].showGridLines = True

    ws1.merge_cells("A1:H2")
    ws1["A1"] = _tr(
        "BÁO CÁO TỐI ƯU HÓA DANH MỤC ĐẦU TƯ THEO MÔ HÌNH MARKOWITZ (MVO)",
        "MARKOWITZ MEAN-VARIANCE PORTFOLIO OPTIMIZATION REPORT (MVO)",
    )
    _style_range(ws1, 1, 1, 8, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    ws1["A4"] = _tr("THÔNG SỐ CẤU HÌNH, NGUỒN DỮ LIỆU & PHIÊN TÍNH", "CONFIGURATION, DATA PROVENANCE & RUN SNAPSHOT")
    ws1["A4"].font = sec_font

    meta_rows = [
        (
            _tr("Thời điểm tính / Run ID", "Computed At / Run ID"),
            f"{computed_at} [{run_id}]",
            _tr("Quy chuẩn năm hóa", "Annualization"),
            _tr("252 phiên / năm", "252 sessions / yr"),
            _tr("Nguồn dữ liệu", "Data Source"),
            f"{data_meta.get('source', 'N/A')} ({data_meta.get('from_date') or '—'} → {data_meta.get('to_date') or '—'})",
        ),
        (
            _tr("Quy mô vốn đầu tư (NAV)", "Total Capital (NAV)"),
            nav_vnd,
            _tr("Lãi suất phi rủi ro (Rf)", "Risk-Free Rate (Rf)"),
            rf,
            _tr("Trạng thái Tangency", "Tangency Status"),
            _tr("Hợp lệ (Excess Return > 0)", "Valid (Positive Excess)") if tan_status == "optimal" else _tr("Mọi danh mục có E(R) <= Rf (Ưu tiên Cash)", "All portfolios E(R) <= Rf (Cash Preferred)"),
        ),
        (
            _tr("Chế độ Tối ưu", "Optimization Mode"),
            _tr("Tham chiếu Bán khống (Học thuật)", "Short-Selling Academic Reference") if allow_short else _tr("Long-Only + Giới hạn tỷ trọng", "Long-Only Box-Constrained"),
            _tr("Hệ số ngại rủi ro (γ)", "Risk Aversion (γ)"),
            gamma,
            _tr("Trạng thái Merton / Dữ liệu", "Merton / Data Alignment"),
            f"Merton: {merton_status} | Dropped days: {data_meta.get('dropped_days_count', 0)}",
        ),
    ]
    for idx, (k1, v1, k2, v2, k3, v3) in enumerate(meta_rows, start=5):
        ws1.cell(row=idx, column=1, value=k1).font = bold_font
        c1 = ws1.cell(row=idx, column=2, value=v1)
        c1.font = reg_font
        if isinstance(v1, float) and v1 > 1000:
            c1.number_format = "#,##0"
        ws1.cell(row=idx, column=4, value=k2).font = bold_font
        c2 = ws1.cell(row=idx, column=5, value=v2)
        c2.font = reg_font
        if "(Rf)" in k2:
            c2.number_format = "0.00%"
        elif isinstance(v2, float):
            c2.number_format = "0.00"
        ws1.cell(row=idx, column=6, value=k3).font = bold_font
        ws1.merge_cells(start_row=idx, start_column=7, end_row=idx, end_column=8)
        ws1.cell(row=idx, column=7, value=v3).font = reg_font
        _style_range(ws1, 1, idx, 8, idx, border=thin_border)

    # KPI Summary Comparison Table
    ws1["A9"] = _tr("BẢNG SO SÁNH DANH MỤC LÝ THUYẾT, MỤC TIÊU & THỰC THI SAU PHÍ", "PORTFOLIO COMPARISON: THEORETICAL, TARGET COMPLETE & POST-FEE EXECUTED")
    ws1["A9"].font = sec_font

    kpi_headers = [
        _tr("Chỉ tiêu Đo lường", "Metric"),
        "GMV",
        _tr("Tangency (Tham chiếu CP)", "Tangency (Equity Ref)"),
        _tr("Complete (Mục tiêu y*)", "Complete (Target y*)"),
        _tr("Complete (Sau Lô 100 & Phí)", "Executed (Post-Fee)"),
        "Equal Weight (1/N)",
    ]
    for col_i, h in enumerate(kpi_headers, start=1):
        c = ws1.cell(row=10, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center")

    kpi_data = [
        (_tr("Tỷ suất sinh lợi kỳ vọng E(Rp)", "Expected Return E(Rp)"), gmv["expected_return"], tan["expected_return"], comp["expected_return"], exec_ret, eq["expected_return"], "0.00%"),
        (_tr("Độ lệch chuẩn (Volatility σp)", "Volatility σp"), gmv["volatility"], tan["volatility"], comp["volatility"], exec_vol, eq["volatility"], "0.00%"),
        (_tr("Phương sai danh mục (σp²)", "Variance σp²"), gmv["variance"], tan["variance"], comp["variance"], exec_var, eq["variance"], "0.0000"),
        (_tr("Tỷ số Sharpe [(E(Rp) - Rf) / σp]", "Sharpe Ratio [(E(Rp) - Rf) / σp]"), gmv["sharpe_ratio"], tan["sharpe_ratio"], comp["sharpe_ratio"], exec_sr, eq["sharpe_ratio"], "0.000"),
        (_tr("Tỷ trọng Cổ phiếu Rủi ro (y)", "Risky Equity Weight (y)"), 1.0, 1.0, comp["y_star_risky_weight"], y_exec, 1.0, "0.00%"),
        (_tr("Tỷ trọng Tiền mặt (1 - y)", "Cash / Rf Weight (1 - y)"), 0.0, 0.0, comp["w_rf_weight"], (exec_cash_post if exec_ready else None), 0.0, "0.00%"),
    ]
    for offset, (metric_name, v_gmv, v_tan, v_comp, v_exec, v_eq, fmt) in enumerate(kpi_data, start=11):
        ws1.cell(row=offset, column=1, value=metric_name).font = bold_font
        for c_i, val in enumerate([v_gmv, v_tan, v_comp, v_exec, v_eq], start=2):
            cell = ws1.cell(row=offset, column=c_i, value=(float(val) if val is not None else "N/A"))
            cell.font = reg_font
            if val is not None:
                cell.number_format = fmt
            else:
                cell.alignment = Alignment(horizontal="center")
        _style_range(ws1, 1, offset, 6, offset, border=thin_border)

    # Asset Allocation Table (Rows start 20 -> tot_row stays 21 + n, i.e. D26 for n=5)
    ws1["A18"] = _tr("BẢNG PHÂN BỔ TỶ TRỌNG CHI TIẾT TỪNG TÀI SẢN", "DETAILED ASSET WEIGHT ALLOCATION")
    ws1["A18"].font = sec_font

    alloc_headers = [
        _tr("Mã Tài sản", "Asset"),
        _tr("E(Ri) Năm", "Annual E(Ri)"),
        _tr("Độ lệch chuẩn σi", "Annual σi"),
        _tr("Tỷ trọng GMV", "GMV Weight"),
        _tr("Tỷ trọng Tangency", "Tangency Weight"),
        _tr("Complete Mục tiêu (y*)", "Complete Target (y*)"),
        _tr("Tỷ trọng Đều (1/N)", "Equal Weight (1/N)"),
        _tr("Thực thi Sau phí (NAV')", "Executed Post-Fee"),
    ]
    for col_i, h in enumerate(alloc_headers, start=1):
        c = ws1.cell(row=19, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center")

    start_alloc_row = 20
    for i, sym in enumerate(symbols):
        r = start_alloc_row + i
        ws1.cell(row=r, column=1, value=sym).font = bold_font
        ws1.cell(row=r, column=2, value=float(mu[i])).number_format = "0.00%"
        ws1.cell(row=r, column=3, value=float(std[i])).number_format = "0.00%"
        ws1.cell(row=r, column=4, value=float(gmv["weights"][i])).number_format = "0.00%"
        ws1.cell(row=r, column=5, value=float(tan["weights"][i])).number_format = "0.00%"
        ws1.cell(row=r, column=6, value=float(comp["asset_weights"][i])).number_format = "0.00%"
        ws1.cell(row=r, column=7, value=float(eq["weights"][i])).number_format = "0.00%"
        ws1.cell(row=r, column=8, value=(float(exec_w_post[i]) if exec_ready else 0.0)).number_format = "0.00%"
        _style_range(ws1, 1, r, 8, r, border=thin_border, fill=zebra_fill if i % 2 == 1 else None)

    rf_row = start_alloc_row + n
    ws1.cell(row=rf_row, column=1, value="CASH / Risk-Free (Rf)").font = bold_font
    ws1.cell(row=rf_row, column=2, value=float(rf)).number_format = "0.00%"
    ws1.cell(row=rf_row, column=3, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=4, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=5, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=6, value=float(comp["w_rf_weight"])).number_format = "0.00%"
    ws1.cell(row=rf_row, column=7, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=8, value=(exec_cash_post if exec_ready else 1.0)).number_format = "0.00%"
    _style_range(ws1, 1, rf_row, 8, rf_row, border=thin_border)

    tot_row = rf_row + 1
    ws1.cell(row=tot_row, column=1, value=_tr("TỔNG TỶ TRỌNG (SUM)", "TOTAL WEIGHTS (SUM)")).font = bold_font
    for col_i in range(4, 9):
        col_let = get_column_letter(col_i)
        c = ws1.cell(row=tot_row, column=col_i, value=f"=SUM({col_let}{start_alloc_row}:{col_let}{rf_row})")
        c.font = bold_font
        c.number_format = "0.00%"
    _style_range(ws1, 1, tot_row, 8, tot_row, border=thin_border, fill=accent_fill)

    for col_i in range(1, 9):
        ws1.column_dimensions[get_column_letter(col_i)].width = 24

    # =========================================================================
    # SHEET 2: 02_Asset_Statistics
    # =========================================================================
    ws2 = wb.create_sheet(title="02_Asset_Statistics")
    ws2["A1"] = _tr(
        "THỐNG KÊ TỶ SUẤT SINH LỢI & RỦI RO TỪNG TÀI SẢN (QUY NĂM 252 PHIÊN)",
        "INDIVIDUAL ASSET RETURN & VOLATILITY STATISTICS (252-SESSION ANNUALIZED)",
    )
    ws2["A1"].font = sec_font

    stat_headers = [
        _tr("STT", "#"),
        _tr("Mã Cổ phiếu", "Ticker"),
        _tr("Thị giá Thực thi (VNĐ)", "Execution Price (VND)"),
        _tr("E(Ri) Ngày", "Daily Mean Return"),
        _tr("E(Ri) Quy năm (x252)", "Annualized E(Ri)"),
        _tr("CAGR Năm (%)", "Annualized CAGR"),
        _tr("Độ lệch chuẩn σi Năm", "Annualized σi"),
        _tr("Phương sai σi² Năm", "Annualized Variance"),
        _tr("Phần bù E(Ri) - Rf", "Excess Return E(Ri)-Rf"),
        _tr("Sharpe Đơn lẻ", "Standalone Sharpe"),
    ]
    for col_i, h in enumerate(stat_headers, start=1):
        c = ws2.cell(row=3, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center")

    for i, sym in enumerate(symbols):
        r = 4 + i
        er_y = float(mu[i])
        vol_y = float(std[i])
        p_raw = latest_prices.get(sym)
        cagr_i = float(cagr[i]) if (cagr is not None and i < len(cagr) and cagr[i] is not None) else None

        ws2.cell(row=r, column=1, value=i + 1).alignment = Alignment(horizontal="center")
        ws2.cell(row=r, column=2, value=sym).font = bold_font
        if p_raw is not None:
            ws2.cell(row=r, column=3, value=float(p_raw)).number_format = "#,##0"
        else:
            ws2.cell(row=r, column=3, value=_tr("Chưa có giá", "N/A")).alignment = Alignment(horizontal="center")
        ws2.cell(row=r, column=4, value=er_y / 252.0).number_format = "0.000%"
        ws2.cell(row=r, column=5, value=er_y).number_format = "0.00%"
        if cagr_i is not None:
            ws2.cell(row=r, column=6, value=cagr_i).number_format = "0.00%"
        else:
            ws2.cell(row=r, column=6, value="N/A").alignment = Alignment(horizontal="center")
        ws2.cell(row=r, column=7, value=vol_y).number_format = "0.00%"
        ws2.cell(row=r, column=8, value=f"=G{r}^2").number_format = "0.0000"
        ws2.cell(row=r, column=9, value=f"=E{r}-{rf}").number_format = "0.00%"
        ws2.cell(row=r, column=10, value=f"=I{r}/G{r}" if vol_y > 1e-8 else 0.0).number_format = "0.000"
        _style_range(ws2, 1, r, 10, r, border=thin_border)

    for col_i in range(1, 11):
        ws2.column_dimensions[get_column_letter(col_i)].width = 21

    # =========================================================================
    # SHEET 3: 03_Covariance_Correlation
    # =========================================================================
    ws3 = wb.create_sheet(title="03_Covariance_Correlation")
    ws3["A1"] = _tr(
        "1. MA TRẬN HIỆP PHƯƠNG SAI QUY NĂM (ANNUALIZED COVARIANCE MATRIX Σ = Σ_daily * 252)",
        "1. ANNUALIZED COVARIANCE MATRIX (Σ = Σ_daily * 252)",
    )
    ws3["A1"].font = sec_font

    ws3.cell(row=3, column=1, value="Σ (Cov)").fill = sub_fill
    ws3.cell(row=3, column=1).font = tbl_hdr_font
    for i, sym in enumerate(symbols):
        c_top = ws3.cell(row=3, column=2 + i, value=sym)
        c_top.fill = sub_fill
        c_top.font = tbl_hdr_font
        c_top.alignment = Alignment(horizontal="center")

        r_row = 4 + i
        c_side = ws3.cell(row=r_row, column=1, value=sym)
        c_side.font = bold_font
        c_side.fill = zebra_fill
        for j in range(n):
            cell = ws3.cell(row=r_row, column=2 + j, value=float(cov[i][j]))
            cell.number_format = "0.00000"
            cell.font = bold_font if i == j else reg_font
            if i == j:
                cell.fill = accent_fill
        _style_range(ws3, 1, r_row, n + 1, r_row, border=thin_border)

    corr_start = 4 + n + 3
    ws3.cell(
        row=corr_start - 1,
        column=1,
        value=_tr("2. MA TRẬN HỆ SỐ TƯƠNG QUAN (CORRELATION MATRIX P)", "2. CORRELATION MATRIX (P)"),
    ).font = sec_font
    ws3.cell(row=corr_start, column=1, value="P (Corr)").fill = sub_fill
    ws3.cell(row=corr_start, column=1).font = tbl_hdr_font

    for i, sym in enumerate(symbols):
        c_top = ws3.cell(row=corr_start, column=2 + i, value=sym)
        c_top.fill = sub_fill
        c_top.font = tbl_hdr_font
        c_top.alignment = Alignment(horizontal="center")

        r_row = corr_start + 1 + i
        c_side = ws3.cell(row=r_row, column=1, value=sym)
        c_side.font = bold_font
        c_side.fill = zebra_fill
        for j in range(n):
            cell = ws3.cell(row=r_row, column=2 + j, value=float(corr[i][j]))
            cell.number_format = "0.000"
            cell.font = bold_font if i == j else reg_font
            if i == j:
                cell.fill = accent_fill
        _style_range(ws3, 1, r_row, n + 1, r_row, border=thin_border)

    for col_i in range(1, n + 3):
        ws3.column_dimensions[get_column_letter(col_i)].width = 16

    # =========================================================================
    # SHEET 4: 04_Matrix_Calculations (Merton Theoretical Reference Only)
    # =========================================================================
    ws4 = wb.create_sheet(title="04_Matrix_Calculations")
    ws4["A1"] = _tr(
        "THAM CHIẾU LÝ THUYẾT MERTON (1972) — NGHIỆM GIẢI TÍCH KHÔNG RÀNG BUỘC",
        "THEORETICAL REFERENCE: MERTON (1972) UNCONSTRAINED CLOSED-FORM MATRIX ALGEBRA",
    )
    ws4["A1"].font = sec_font
    ws4.merge_cells("A2:G2")
    ws4["A2"] = _tr(
        "Lưu ý: Bảng này minh họa nghiệm giải tích không ràng buộc (cho phép bán khống) để đối chiếu học thuật; danh mục thực hành tuân theo giới hạn Long-Only / Box trong bảng kết quả.",
        "Note: Unconstrained closed-form analytical solution (allows short-selling) shown strictly for academic comparison against the constrained active portfolio.",
    )
    ws4["A2"].font = warn_font
    ws4["A2"].fill = warn_fill

    if merton_status == "singular_covariance" or inv_cov is None or scalars is None:
        ws4["A4"] = _tr(
            "KHÔNG XÁC ĐỊNH: Ma trận hiệp phương sai Σ suy biến hoặc điều kiện số quá lớn (không khả nghịch), không thể tính nghịch đảo giải tích Σ⁻¹ và các đại lượng A, B, C, D. Bộ giải QP Long-Only vẫn hoạt động bình thường.",
            "UNAVAILABLE: Covariance matrix Σ is singular/ill-conditioned (non-invertible); analytical Σ⁻¹ and Merton scalars A, B, C, D are undefined. Constrained QP remains valid.",
        )
        ws4["A4"].font = warn_font
        ws4.column_dimensions["A"].width = 48
    else:
        ws4["A4"] = _tr("1. MA TRẬN NGHỊCH ĐẢO HIỆP PHƯƠNG SAI (Σ⁻¹ = MINVERSE(Σ))", "1. INVERSE COVARIANCE MATRIX (Σ⁻¹)")
        ws4["A4"].font = bold_font

        ws4.cell(row=5, column=1, value="Σ⁻¹").fill = sub_fill
        ws4.cell(row=5, column=1).font = tbl_hdr_font
        for i, sym in enumerate(symbols):
            c_top = ws4.cell(row=5, column=2 + i, value=sym)
            c_top.fill = sub_fill
            c_top.font = tbl_hdr_font
            c_top.alignment = Alignment(horizontal="center")

            r_row = 6 + i
            ws4.cell(row=r_row, column=1, value=sym).font = bold_font
            for j in range(n):
                cell = ws4.cell(row=r_row, column=2 + j, value=float(inv_cov[i][j]))
                cell.number_format = "0.0000"
                cell.font = reg_font
            _style_range(ws4, 1, r_row, n + 1, r_row, border=thin_border)

        sc_start = 6 + n + 2
        ws4.cell(row=sc_start, column=1, value=_tr("2. ĐẠI LƯỢNG VÔ HƯỚNG MERTON (A, B, C, D)", "2. MERTON SCALARS (A, B, C, D)")).font = sec_font
        sc_headers = [
            _tr("Ký hiệu", "Scalar"),
            _tr("Công thức Ma trận", "Matrix Formula"),
            _tr("Công thức Excel", "Excel Formula"),
            _tr("Giá trị", "Value"),
        ]
        for col_i, h in enumerate(sc_headers, start=1):
            c = ws4.cell(row=sc_start + 1, column=col_i, value=h)
            c.fill = sub_fill
            c.font = tbl_hdr_font

        cov_end_col = get_column_letter(1 + n)
        cov_range_str = f"'03_Covariance_Correlation'!B4:{cov_end_col}{3+n}"
        mu_range_str = f"'02_Asset_Statistics'!E4:E{3+n}"

        merton_rows = [
            ("A", "A = 1ᵀ · Σ⁻¹ · μ", f"=SUM(MMULT(MINVERSE({cov_range_str}), {mu_range_str}))", scalars["A"]),
            ("B", "B = μᵀ · Σ⁻¹ · μ", f"=MMULT(TRANSPOSE({mu_range_str}), MMULT(MINVERSE({cov_range_str}), {mu_range_str}))", scalars["B"]),
            ("C", "C = 1ᵀ · Σ⁻¹ · 1", f"=SUM(MINVERSE({cov_range_str}))", scalars["C"]),
            ("D", "D = B·C - A²", f"=D{sc_start+3}*D{sc_start+4}-D{sc_start+2}^2", scalars["D"]),
        ]
        for offset, (sym_k, math_expr, xl_expr, val) in enumerate(merton_rows, start=sc_start + 2):
            ws4.cell(row=offset, column=1, value=sym_k).font = bold_font
            ws4.cell(row=offset, column=2, value=math_expr).font = reg_font
            ws4.cell(row=offset, column=3, value=xl_expr).font = formula_font
            c_val = ws4.cell(row=offset, column=4, value=float(val))
            c_val.font = bold_font
            c_val.number_format = "0.0000"
            _style_range(ws4, 1, offset, 4, offset, border=thin_border)

        vec_start = sc_start + 8
        ws4.cell(
            row=vec_start,
            column=1,
            value=_tr("3. NGHIỆM THAM CHIẾU MERTON KHÔNG RÀNG BUỘC VS NGHIỆM ĐANG ÁP DỤNG", "3. UNCONSTRAINED MERTON WEIGHTS VS ACTIVE CONSTRAINED PORTFOLIO"),
        ).font = sec_font
        vec_headers = [
            _tr("Mã CP", "Ticker"),
            "μi - Rf",
            "(Σ⁻¹ · 1)i",
            _tr("w_GMV (Merton Không ràng buộc)", "w_GMV (Unconstrained Merton)"),
            "zi = [Σ⁻¹(μ - Rf·1)]i",
            _tr("w_Tangency (Merton Không ràng buộc)", "w_Tangency (Unconstrained Merton)"),
            _tr("w_Tangency Đang áp dụng (QP/Mandate)", "Active Portfolio Equity Weight"),
        ]
        for col_i, h in enumerate(vec_headers, start=1):
            c = ws4.cell(row=vec_start + 1, column=col_i, value=h)
            c.fill = sub_fill
            c.font = tbl_hdr_font

        inv_cov_np = np.array(inv_cov)
        mu_np = np.array(mu)
        ones_np = np.ones(n)
        v_ones = inv_cov_np @ ones_np
        z_vec = inv_cov_np @ (mu_np - rf * ones_np)
        sum_z = float(np.sum(z_vec)) if abs(float(np.sum(z_vec))) > 1e-9 else 1.0

        for i, sym in enumerate(symbols):
            r = vec_start + 2 + i
            ws4.cell(row=r, column=1, value=sym).font = bold_font
            ws4.cell(row=r, column=2, value=float(mu[i] - rf)).number_format = "0.00%"
            ws4.cell(row=r, column=3, value=float(v_ones[i])).number_format = "0.0000"
            ws4.cell(row=r, column=4, value=float(v_ones[i] / scalars["C"])).number_format = "0.00%"
            ws4.cell(row=r, column=5, value=float(z_vec[i])).number_format = "0.0000"
            ws4.cell(row=r, column=6, value=float(z_vec[i] / sum_z)).number_format = "0.00%"
            ws4.cell(row=r, column=7, value=float(tan["weights"][i])).number_format = "0.00%"
            _style_range(ws4, 1, r, 7, r, border=thin_border)

        for col_i in range(1, 8):
            ws4.column_dimensions[get_column_letter(col_i)].width = 25

    # =========================================================================
    # SHEET 5: 05_Efficient_Frontier_Data
    # =========================================================================
    ws5 = wb.create_sheet(title="05_Efficient_Frontier_Data")
    ws5["A1"] = _tr(
        "TỌA ĐỘ ĐƯỜNG BIÊN HIỆU QUẢ (MARKOWITZ EFFICIENT FRONTIER)",
        "MARKOWITZ EFFICIENT FRONTIER COORDINATES",
    )
    ws5["A1"].font = sec_font

    ef_headers = [
        _tr("Điểm #", "#"),
        _tr("Độ biến động σp", "Volatility σp"),
        _tr("Tỷ suất sinh lợi E(Rp)", "Expected Return E(Rp)"),
        _tr("Tỷ số Sharpe", "Sharpe Ratio"),
        _tr("Nhánh Hiệu quả", "Branch"),
    ] + [f"w({s})" for s in symbols]
    for col_i, h in enumerate(ef_headers, start=1):
        c = ws5.cell(row=3, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font

    frontier_pts = analysis_data["frontier"]
    for idx, pt in enumerate(frontier_pts, start=4):
        ws5.cell(row=idx, column=1, value=idx - 3)
        ws5.cell(row=idx, column=2, value=float(pt["volatility"])).number_format = "0.00%"
        ws5.cell(row=idx, column=3, value=float(pt["return"])).number_format = "0.00%"
        ws5.cell(row=idx, column=4, value=float(pt["sharpe"])).number_format = "0.000"
        ws5.cell(row=idx, column=5, value="Efficient" if pt.get("is_efficient", True) else "Inefficient")
        for s_i, w_val in enumerate(pt.get("weights", [])):
            ws5.cell(row=idx, column=6 + s_i, value=float(w_val)).number_format = "0.0%"
        _style_range(ws5, 1, idx, 5 + n, idx, border=thin_border)

    if len(frontier_pts) >= 3:
        chart = ScatterChart()
        chart.title = "Markowitz Efficient Frontier"
        chart.style = 13
        chart.x_axis.title = "Volatility (σp)"
        chart.y_axis.title = "Expected Return E(Rp)"
        xvalues = Reference(ws5, min_col=2, min_row=4, max_row=3 + len(frontier_pts))
        yvalues = Reference(ws5, min_col=3, min_row=4, max_row=3 + len(frontier_pts))
        series = Series(yvalues, xvalues, title="Efficient Frontier")
        chart.series.append(series)
        chart.width = 18
        chart.height = 11
        ws5.add_chart(chart, f"{get_column_letter(7 + n)}3")

    for col_i in range(1, 6 + n):
        ws5.column_dimensions[get_column_letter(col_i)].width = 16

    # =========================================================================
    # SHEET 6: 06_Execution_Order_Sheet (Reads directly from execution_engine)
    # =========================================================================
    ws6 = wb.create_sheet(title="06_Execution_Order_Sheet")
    ws6["A1"] = _tr(
        "BẢNG PHÂN BỔ LỆNH MUA LÔ CHẴN 100 & ĐỐI SOÁT TIỀN MẶT / PHÍ (MÔ PHỎNG)",
        "LOT-100 EXECUTION SIMULATION & CASH / BUY-FEE RECONCILIATION",
    )
    ws6["A1"].font = sec_font

    if not exec_ready:
        ws6["A3"] = _tr("TRẠNG THÁI BẢNG THỰC THI: VÔ HIỆU HÓA", "EXECUTION STATUS: DISABLED")
        ws6["A3"].font = warn_font
        ws6["A4"] = execution.get("disabled_reason") or _tr("Không đủ điều kiện chia lô.", "Cannot compute lot execution.")
        ws6["A4"].font = reg_font
        ws6.column_dimensions["A"].width = 64
    else:
        fee_pct_str = f"{float(execution.get('buy_fee_rate', 0.0015)) * 100:.2f}%"
        ord_headers = [
            _tr("Mã CP", "Ticker"),
            _tr("Giá Thị trường / Giả định (VNĐ)", "Execution Price (VND)"),
            _tr("Ngày giá", "Price Date"),
            _tr("Tỷ trọng Rổ CP (%)", "Equity Weight (%)"),
            _tr("Tỷ trọng Complete y* (%)", "Complete Target y* (%)"),
            _tr("Giá trị Mục tiêu (VNĐ)", "Target Value (VND)"),
            _tr("Số CP (Lô 100)", "Shares (Lot 100)"),
            _tr("Giá trị Mua Thực tế (VNĐ)", "Purchase Value (VND)"),
            f"{_tr('Phí Mua', 'Buy Fee')} ({fee_pct_str})",
            _tr("Tỷ trọng Sau phí (% NAV')", "Post-Fee Weight (% NAV')"),
        ]
        for col_i, h in enumerate(ord_headers, start=1):
            c = ws6.cell(row=3, column=col_i, value=h)
            c.fill = sub_fill
            c.font = tbl_hdr_font
            c.alignment = Alignment(horizontal="center")

        orders = execution.get("orders", [])
        nav_post = float(execution.get("nav_post_fee", nav_vnd))
        for i, ord_row in enumerate(orders):
            r = 4 + i
            ws6.cell(row=r, column=1, value=ord_row["symbol"]).font = bold_font
            p_v = ord_row.get("price_vnd")
            if p_v is not None:
                ws6.cell(row=r, column=2, value=float(p_v)).number_format = "#,##0"
            else:
                ws6.cell(row=r, column=2, value="N/A").alignment = Alignment(horizontal="center")
            ws6.cell(row=r, column=3, value=ord_row.get("price_date") or "—").alignment = Alignment(horizontal="center")
            ws6.cell(row=r, column=4, value=float(ord_row["w_equity_target"])).number_format = "0.00%"
            ws6.cell(row=r, column=5, value=float(ord_row["w_complete_target"])).number_format = "0.00%"
            ws6.cell(row=r, column=6, value=float(ord_row["target_value_vnd"])).number_format = "#,##0"
            ws6.cell(row=r, column=7, value=int(ord_row["shares"])).number_format = "#,##0"
            ws6.cell(row=r, column=8, value=float(ord_row["purchase_value_vnd"])).number_format = "#,##0"
            ws6.cell(row=r, column=9, value=float(ord_row["buy_fee_vnd"])).number_format = "#,##0"
            ws6.cell(row=r, column=10, value=float(ord_row["actual_weight_post_fee"])).number_format = "0.00%"
            _style_range(ws6, 1, r, 10, r, border=thin_border)

        cash_r = 4 + len(orders)
        ws6.cell(row=cash_r, column=1, value="CASH / Tiền mặt Còn lại (Sau phí)").font = bold_font
        ws6.cell(row=cash_r, column=5, value=float(comp["w_rf_weight"])).number_format = "0.00%"
        ws6.cell(row=cash_r, column=6, value=float(execution.get("target_cash_vnd", 0.0))).number_format = "#,##0"
        ws6.cell(row=cash_r, column=8, value=float(execution.get("cash_remaining", nav_vnd))).number_format = "#,##0"
        ws6.cell(row=cash_r, column=10, value=float(execution.get("actual_cash_weight_post_fee", 1.0))).number_format = "0.00%"
        _style_range(ws6, 1, cash_r, 10, cash_r, border=thin_border, fill=accent_fill)

        tot_exec_r = cash_r + 1
        ws6.cell(row=tot_exec_r, column=1, value=_tr("TỔNG ĐỐI SOÁT NAV SAU PHÍ (NAV' = Mua + Tiền dư)", "RECONCILED POST-FEE NAV' (Purchase + Cash)")).font = bold_font
        ws6.cell(row=tot_exec_r, column=8, value=nav_post).number_format = "#,##0"
        ws6.cell(row=tot_exec_r, column=9, value=float(execution.get("total_buy_fees", 0.0))).number_format = "#,##0"
        ws6.cell(row=tot_exec_r, column=10, value=f"=SUM(J4:J{cash_r})").number_format = "0.00%"
        _style_range(ws6, 1, tot_exec_r, 10, tot_exec_r, border=thin_border, fill=zebra_fill)

        for col_i in range(1, 11):
            ws6.column_dimensions[get_column_letter(col_i)].width = 23

    # =========================================================================
    # SHEET 7: 07_Benchmark_Scorecard
    # =========================================================================
    bm_data: dict[str, Any] = analysis_data.get("benchmark_comparison", {}) or {}
    ws7 = wb.create_sheet(title="07_Benchmark_Scorecard")
    ws7.views.sheetView[0].showGridLines = True

    ws7.merge_cells("A1:D2")
    ws7["A1"] = _tr(
        "BẢNG ĐÁNH GIÁ HIỆU QUẢ TƯƠNG ĐỐI VỚI CHỈ SỐ THỊ TRƯỜNG (BENCHMARK SCORECARD)",
        "RELATIVE PERFORMANCE VS MARKET INDEX (BENCHMARK SCORECARD)",
    )
    _style_range(ws7, 1, 1, 4, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    bm_sym = bm_data.get("benchmark_symbol", "VNINDEX")
    bm_name = bm_data.get("benchmark_name", "VN-Index (HOSE Composite)")
    bm_rng = bm_data.get("benchmark_range", "1Y")
    ws7["A4"] = f"{bm_name} ({bm_sym}) — Horizon: {bm_rng} | {bm_data.get('benchmark_price_type', '')}"
    ws7["A4"].font = sec_font

    if bm_data.get("status") != "available":
        ws7["A6"] = _tr("KHÔNG KHẢ DỤNG ĐỐI CHIẾU BENCHMARK", "BENCHMARK COMPARISON UNAVAILABLE")
        ws7["A6"].font = warn_font
        ws7["A7"] = bm_data.get("message") or _tr("Không có chuỗi dữ liệu lịch sử.", "No historical return series.")
        ws7["A7"].font = reg_font
        for col_i, w in enumerate([44, 28, 28, 30], start=1):
            ws7.column_dimensions[get_column_letter(col_i)].width = w
    else:
        ws7["A5"] = f"{bm_data.get('evaluation_scope', '')} | {bm_data.get('rebalance_assumption', '')}"
        ws7["A5"].font = reg_font

        bm_hdrs = [
            _tr("Chỉ Tiêu Đánh Giá (Metric)", "Metric"),
            _tr("Rổ Cổ phiếu Tham chiếu", "Reference Equity Basket"),
            f"Benchmark ({bm_sym})",
            _tr("Chênh Lệch / Ghi chú", "Spread / Note"),
        ]
        for col_i, h in enumerate(bm_hdrs, start=1):
            c = ws7.cell(row=6, column=col_i, value=h)
            c.fill = sub_fill
            c.font = tbl_hdr_font
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = thin_border

        p_ret = float(bm_data["portfolio_return"])
        b_ret = float(bm_data["benchmark_return"])
        act_ret = float(bm_data["active_return"])
        p_vol = float(bm_data["portfolio_volatility"])
        b_vol = float(bm_data["benchmark_volatility"])
        p_sr = float(bm_data["portfolio_sharpe"])
        b_sr = float(bm_data["benchmark_sharpe"])
        sr_spread = float(bm_data["sharpe_spread"])
        beta_val = float(bm_data["beta"])
        alpha_val = float(bm_data["jensen_alpha"])
        te_val = float(bm_data["tracking_error"])
        ir_val = float(bm_data["information_ratio"])
        corr_bm = float(bm_data["correlation"])
        r2_bm = float(bm_data["r_squared"])

        score_rows = [
            (_tr("Lợi suất Kỳ vọng Năm hóa E(R)", "Annualized Return"), p_ret, b_ret, act_ret, "0.00%"),
            (_tr("Độ biến động Năm hóa (Volatility σ)", "Annualized Volatility"), p_vol, b_vol, p_vol - b_vol, "0.00%"),
            (_tr("Tỷ số Sharpe", "Sharpe Ratio"), p_sr, b_sr, sr_spread, "0.000"),
            ("Active Return (Rp - Rm)", act_ret, 0.0, "Outperform" if act_ret >= 0 else "Underperform", "0.00%"),
            ("Jensen's Alpha", alpha_val, 0.0, "Positive" if alpha_val >= 0 else "Negative", "0.00%"),
            ("Beta (βp)", beta_val, 1.0, "High Beta" if beta_val > 1.05 else ("Low Beta" if beta_val < 0.95 else "Market-Like"), "0.000"),
            ("Tracking Error (TE)", te_val, 0.0, "Active Risk", "0.00%"),
            ("Information Ratio (IR)", ir_val, 0.0, "Strong (>=0.5)" if ir_val >= 0.5 else "Moderate/Neg", "0.000"),
            ("Correlation (ρ)", corr_bm, 1.0, f"R² = {r2_bm * 100:.1f}%", "0.000"),
            ("R-Squared (R²)", r2_bm, 1.0, "Explanatory power", "0.00%"),
        ]

        for idx, (m_label, v_port, v_bm, v_diff, num_fmt) in enumerate(score_rows, start=7):
            ws7.cell(row=idx, column=1, value=m_label).font = bold_font
            c2 = ws7.cell(row=idx, column=2, value=v_port)
            c2.number_format = num_fmt
            c2.font = bold_font
            c3 = ws7.cell(row=idx, column=3, value=v_bm)
            c3.number_format = num_fmt
            c3.font = reg_font
            c4 = ws7.cell(row=idx, column=4, value=v_diff)
            if isinstance(v_diff, float):
                c4.number_format = num_fmt
                c4.font = bold_font
            else:
                c4.font = reg_font
            _style_range(ws7, 1, idx, 4, idx, border=thin_border, fill=zebra_fill if idx % 2 == 1 else None)

        cum_block = bm_data.get("cumulative_series", {})
        c_dates = cum_block.get("dates", [])
        c_port = cum_block.get("portfolio_base100", [])
        c_bm = cum_block.get("benchmark_base100", [])

        if c_dates and len(c_dates) == len(c_port) == len(c_bm):
            ws7["A19"] = f"CUMULATIVE WEALTH INDEX (BASE = 100 AT {c_dates[0]}, {bm_data.get('sessions_compared', len(c_dates)-1)} SESSIONS)"
            ws7["A19"].font = sec_font
            series_hdrs = ["Date", "Reference Portfolio (Base=100)", f"{bm_sym} (Base=100)", "Spread"]
            for col_i, h in enumerate(series_hdrs, start=1):
                c = ws7.cell(row=20, column=col_i, value=h)
                c.fill = navy_fill
                c.font = tbl_hdr_font
                c.alignment = Alignment(horizontal="center")
                c.border = thin_border
            for s_idx, (dt_s, vp, vb) in enumerate(zip(c_dates, c_port, c_bm), start=21):
                ws7.cell(row=s_idx, column=1, value=dt_s).alignment = Alignment(horizontal="center")
                ws7.cell(row=s_idx, column=2, value=float(vp)).number_format = "0.00"
                ws7.cell(row=s_idx, column=3, value=float(vb)).number_format = "0.00"
                ws7.cell(row=s_idx, column=4, value=float(vp) - float(vb)).number_format = "+0.00;-0.00;0.00"
                _style_range(ws7, 1, s_idx, 4, s_idx, border=thin_border, font=reg_font)

        for col_i, w in enumerate([44, 28, 28, 30], start=1):
            ws7.column_dimensions[get_column_letter(col_i)].width = w

    # =========================================================================
    # SHEET 8: 08_Stress_Testing_VaR
    # =========================================================================
    st_root: dict[str, Any] = analysis_data.get("stress_testing", {}) or {}
    profiles = st_root.get("profiles") or {}
    st_data = profiles.get(basis_key) or profiles.get("target_complete") or st_root
    var_m: dict[str, Any] = st_data.get("var_metrics", {}) or {}
    scenarios_list: list[dict[str, Any]] = st_data.get("scenarios", []) or []
    basis_nav = float(st_data.get("nav_vnd", nav_vnd))

    ws8 = wb.create_sheet(title="08_Stress_Testing_VaR")
    ws8.views.sheetView[0].showGridLines = True

    ws8.merge_cells("A1:H2")
    ws8["A1"] = _tr(
        "BÁO CÁO KIỂM ĐỊNH ÁP LỰC (STRESS TESTING) & RỦI RO ĐUÔI (VALUE AT RISK / ES)",
        "STRESS TESTING & TAIL-RISK REPORT (VALUE AT RISK / EXPECTED SHORTFALL)",
    )
    _style_range(ws8, 1, 1, 8, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    basis_display = _tr("Complete Mục tiêu", "Target Complete") if st_data.get("basis") != "executed_post_fee" else _tr("Danh mục Thực thi Sau phí", "Executed Post-Fee")
    ws8["A4"] = f"1. TAIL-RISK METRICS ({basis_display}) — {st_data.get('method', '')} | 21d: {st_data.get('horizon_21d_method', '')}"
    ws8["A4"].font = sec_font
    warnings_list = st_data.get("sample_warnings", [])
    if warnings_list:
        ws8["A5"] = " | ".join(warnings_list)
        ws8["A5"].font = warn_font

    var_hdrs = [
        _tr("Chỉ Số Rủi Ro (Risk Metric)", "Risk Metric"),
        _tr("Tỷ Lệ Tổn Thất 1 Ngày (%)", "1-Day Loss (%)"),
        _tr("Giá Trị Rủi Ro 1 Ngày (VNĐ)", "1-Day Loss (VND)"),
        _tr("Tỷ Lệ Tổn Thất 21 Phiên (%)", "21-Session Loss (%)"),
        _tr("Giá Trị Rủi Ro 21 Phiên (VNĐ)", "21-Session Loss (VND)"),
        _tr("Ghi chú Phương pháp", "Methodology Note"),
    ]
    for col_i, h in enumerate(var_hdrs, start=1):
        c = ws8.cell(row=6, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    var_rows = [
        (
            "Value at Risk (VaR 95%)",
            var_m.get("var_95_1d_pct"),
            var_m.get("var_95_1d_vnd"),
            var_m.get("var_95_21d_pct"),
            var_m.get("var_95_21d_vnd"),
            _tr("Ngưỡng tổn thất ở phân vị 5% tệ nhất", "5th percentile worst loss threshold"),
        ),
        (
            "Value at Risk (VaR 99%)",
            var_m.get("var_99_1d_pct"),
            var_m.get("var_99_1d_vnd"),
            var_m.get("var_99_21d_pct"),
            var_m.get("var_99_21d_vnd"),
            _tr("Ngưỡng tổn thất ở phân vị 1% tệ nhất", "1st percentile extreme loss threshold"),
        ),
        (
            "Expected Shortfall / CVaR (95%)",
            var_m.get("cvar_95_1d_pct"),
            var_m.get("cvar_95_1d_vnd"),
            var_m.get("cvar_95_21d_pct"),
            var_m.get("cvar_95_21d_vnd"),
            _tr("Tổn thất trung bình trong vùng đuôi 5%", "Mean loss conditional on worst 5% tail"),
        ),
        (
            "Expected Shortfall / CVaR (99%)",
            var_m.get("cvar_99_1d_pct"),
            var_m.get("cvar_99_1d_vnd"),
            var_m.get("cvar_99_21d_pct"),
            var_m.get("cvar_99_21d_vnd"),
            _tr("Tổn thất trung bình trong vùng đuôi 1%", "Mean loss conditional on worst 1% tail"),
        ),
    ]

    for idx, (lbl, p1, v1, p21, v21, desc) in enumerate(var_rows, start=7):
        ws8.cell(row=idx, column=1, value=lbl).font = bold_font
        if p1 is not None and v1 is not None:
            c_p1 = ws8.cell(row=idx, column=2, value=-abs(float(p1)))
            c_p1.number_format = "0.00%"
            c_p1.font = bold_font
            c_v1 = ws8.cell(row=idx, column=3, value=-abs(float(v1)))
            c_v1.number_format = "#,##0"
            c_v1.font = reg_font
        else:
            ws8.cell(row=idx, column=2, value="N/A")
            ws8.cell(row=idx, column=3, value="N/A")

        if p21 is not None and v21 is not None:
            c_p21 = ws8.cell(row=idx, column=4, value=-abs(float(p21)))
            c_p21.number_format = "0.00%"
            c_p21.font = bold_font
            c_v21 = ws8.cell(row=idx, column=5, value=-abs(float(v21)))
            c_v21.number_format = "#,##0"
            c_v21.font = reg_font
        else:
            ws8.cell(row=idx, column=4, value="N/A")
            ws8.cell(row=idx, column=5, value="N/A")

        ws8.cell(row=idx, column=6, value=desc).font = reg_font
        _style_range(ws8, 1, idx, 6, idx, border=thin_border, fill=zebra_fill if idx % 2 == 1 else None)

    mdd_comp = var_m.get("max_drawdown_complete_pct")
    mdd_risky = var_m.get("max_drawdown_risky_pct")

    ws8.cell(row=11, column=1, value="Maximum Drawdown (Complete / Active)").font = bold_font
    if mdd_comp is not None:
        ws8.cell(row=11, column=2, value=-abs(float(mdd_comp))).number_format = "0.00%"
        ws8.cell(row=11, column=3, value=-abs(float(mdd_comp) * basis_nav)).number_format = "#,##0"
    else:
        ws8.cell(row=11, column=2, value="N/A")
        ws8.cell(row=11, column=3, value=_tr("Không tính khi thiếu chuỗi giá", "N/A (No price history)"))
    ws8.cell(row=11, column=6, value=_tr("Sụt giảm đỉnh-đáy lịch sử của danh mục tổng thể", "Historical peak-to-trough drawdown of portfolio")).font = reg_font
    _style_range(ws8, 1, 11, 6, 11, border=thin_border)

    ws8.cell(row=12, column=1, value="Maximum Drawdown (Equity Basket)").font = bold_font
    if mdd_risky is not None:
        ws8.cell(row=12, column=2, value=-abs(float(mdd_risky))).number_format = "0.00%"
        ws8.cell(row=12, column=3, value=-abs(float(mdd_risky) * basis_nav)).number_format = "#,##0"
    else:
        ws8.cell(row=12, column=2, value="N/A")
        ws8.cell(row=12, column=3, value=_tr("Không tính khi thiếu chuỗi giá", "N/A (No price history)"))
    ws8.cell(row=12, column=6, value=_tr("Sụt giảm đỉnh-đáy lịch sử của phần cổ phiếu", "Historical peak-to-trough drawdown of equity basket")).font = reg_font
    _style_range(ws8, 1, 12, 6, 12, border=thin_border, fill=zebra_fill)

    ws8["A15"] = _tr("2. KIỂM ĐỊNH CÚ SỐC CHỈ SỐ THEO MÔ HÌNH BETA LỊCH SỬ", "2. BETA-MODEL INDEX SHOCK SCENARIOS")
    ws8["A15"].font = sec_font

    if st_data.get("stress_status") != "available" or not scenarios_list:
        ws8["A16"] = _tr(
            "Không khả dụng: Chế độ ma trận tham số (không có chuỗi lịch sử) hoặc Benchmark lỗi nên không ước lượng được Beta thực nghiệm.",
            "Unavailable: Empirical Beta cannot be estimated without aligned historical return series.",
        )
        ws8["A16"].font = warn_font
    else:
        sc_hdrs = [
            _tr("Kịch Bản Cú Sốc Lịch Sử", "Crisis Scenario"),
            _tr("Giai Đoạn", "Period"),
            _tr("Cú Sốc Thị Trường", "Market Shock"),
            _tr("Tác Động Rổ CP (%)", "Equity Basket Impact"),
            _tr("Tác Động Tổng Thể (%)", "Total Portfolio Impact"),
            _tr("Tổn Thất Ước Tính (VNĐ)", "Est. Loss (VND)"),
            _tr("NAV Còn Lại (VNĐ)", "Post-Shock NAV (VND)"),
            _tr("Đệm Tiền Mặt Bảo Vệ (VNĐ)", "Cash Cushion (VND)"),
        ]
        for col_i, h in enumerate(sc_hdrs, start=1):
            c = ws8.cell(row=16, column=col_i, value=h)
            c.fill = navy_fill
            c.font = tbl_hdr_font
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = thin_border

        for s_idx, sc in enumerate(scenarios_list, start=17):
            ws8.cell(row=s_idx, column=1, value=sc.get("name", "")).font = bold_font
            ws8.cell(row=s_idx, column=2, value=sc.get("period", "")).alignment = Alignment(horizontal="center")
            ws8.cell(row=s_idx, column=3, value=float(sc.get("market_shock_pct", 0.0))).number_format = "0.00%"
            ws8.cell(row=s_idx, column=4, value=float(sc.get("risky_only_impact_pct", 0.0))).number_format = "0.00%"
            c_cp = ws8.cell(row=s_idx, column=5, value=float(sc.get("complete_impact_pct", 0.0)))
            c_cp.number_format = "0.00%"
            c_cp.font = bold_font
            c_loss = ws8.cell(row=s_idx, column=6, value=-abs(float(sc.get("estimated_loss_vnd", 0.0))))
            c_loss.number_format = "#,##0"
            c_loss.font = bold_font
            ws8.cell(row=s_idx, column=7, value=float(sc.get("post_shock_nav_vnd", 0.0))).number_format = "#,##0"
            ws8.cell(row=s_idx, column=8, value=float(sc.get("cash_protection_vnd", 0.0))).number_format = "#,##0"
            _style_range(ws8, 1, s_idx, 8, s_idx, border=thin_border, fill=zebra_fill if s_idx % 2 == 1 else None)

    for col_i, w in enumerate([40, 20, 22, 24, 26, 24, 26, 26], start=1):
        ws8.column_dimensions[get_column_letter(col_i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
