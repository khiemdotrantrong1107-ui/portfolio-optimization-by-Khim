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
import math
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def export_mvo_institutional_workbook(analysis_data: dict[str, Any]) -> bytes:
    """Build the complete 6-sheet institutional Excel report."""
    wb = Workbook()

    # Palette & Typography
    navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    accent_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    title_font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    sec_font = Font(name="Segoe UI", size=11, bold=True, color="0F172A")
    tbl_hdr_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    reg_font = Font(name="Segoe UI", size=10, color="1E293B")
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
    std: list[float] = analysis_data["std"]
    cov: list[list[float]] = analysis_data["cov"]
    corr: list[list[float]] = analysis_data["corr"]
    inv_cov: list[list[float]] = analysis_data["inv_cov"]
    scalars: dict[str, float] = analysis_data["merton_scalars"]
    rf: float = analysis_data["rf"]
    risk_aversion_A: float = analysis_data["risk_aversion_A"]
    nav_vnd: float = analysis_data.get("nav_vnd", 1_000_000_000.0)
    allow_short: bool = analysis_data.get("allow_short", False)
    latest_prices: dict[str, float] = analysis_data.get("latest_prices", {})

    gmv = analysis_data["gmv"]
    tan = analysis_data["tangency"]
    comp = analysis_data["complete_portfolio"]
    eq = analysis_data["equal_weight"]

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
    # =========================================================================
    ws1 = wb.active
    ws1.title = "01_Executive_Summary"
    ws1.views.sheetView[0].showGridLines = True

    ws1.merge_cells("A1:G2")
    ws1["A1"] = "BÁO CÁO TỐI ƯU HÓA DANH MỤC ĐẦU TƯ THEO MÔ HÌNH MARKOWITZ (MVO)"
    _style_range(ws1, 1, 1, 7, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    ws1["A4"] = "THÔNG SỐ CẤU HÌNH & CHÍNH SÁCH ĐẦU TƯ"
    ws1["A4"].font = sec_font

    meta_rows = [
        ("Ngày lập báo cáo", datetime.now().strftime("%Y-%m-%d %H:%M"), "Quy chuẩn năm hóa", "252 phiên / năm"),
        ("Quy mô vốn đầu tư (NAV)", nav_vnd, "Lãi suất phi rủi ro (Rf)", rf),
        ("Chế độ Bán khống (Short-Sales)", "Cho phép (Unconstrained)" if allow_short else "Không bán khống (Long-Only)", "Hệ số ngại rủi ro (A)", risk_aversion_A),
    ]
    for idx, (k1, v1, k2, v2) in enumerate(meta_rows, start=5):
        ws1.cell(row=idx, column=1, value=k1).font = bold_font
        c1 = ws1.cell(row=idx, column=2, value=v1)
        c1.font = reg_font
        if isinstance(v1, float) and v1 > 1000:
            c1.number_format = "#,##0"
        ws1.cell(row=idx, column=4, value=k2).font = bold_font
        c2 = ws1.cell(row=idx, column=5, value=v2)
        c2.font = reg_font
        if k2.endswith("(Rf)"):
            c2.number_format = "0.00%"
        elif isinstance(v2, float):
            c2.number_format = "0.00"
        _style_range(ws1, 1, idx, 5, idx, border=thin_border)

    # KPI Summary Comparison Table
    ws1["A9"] = "BẢNG TỔNG HỢP HIỆU SUẤT KỲ VỌNG CÁC DANH MỤC TỐI ƯU"
    ws1["A9"].font = sec_font

    kpi_headers = ["Chỉ tiêu Đo lường", "GMV (Rủi ro Thấp nhất)", "Tangency (Max Sharpe)", "Complete Portfolio (Tối ưu U)", "Equal Weight (1/N)"]
    for col_i, h in enumerate(kpi_headers, start=1):
        c = ws1.cell(row=10, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center")

    kpi_data = [
        ("Tỷ suất sinh lợi kỳ vọng E(Rp)", gmv["expected_return"], tan["expected_return"], comp["expected_return"], eq["expected_return"], "0.00%"),
        ("Độ lệch chuẩn (Volatility σp)", gmv["volatility"], tan["volatility"], comp["volatility"], eq["volatility"], "0.00%"),
        ("Phương sai danh mục (σp²)", gmv["variance"], tan["variance"], comp["variance"], eq["variance"], "0.0000"),
        ("Tỷ số Sharpe [(E(Rp) - Rf) / σp]", gmv["sharpe_ratio"], tan["sharpe_ratio"], comp["sharpe_ratio"], eq["sharpe_ratio"], "0.000"),
        ("Tỷ trọng Tài sản Rủi ro (y*)", 1.0, 1.0, comp["y_star_risky_weight"], 1.0, "0.00%"),
        ("Tỷ trọng Phi rủi ro (1 - y*)", 0.0, 0.0, comp["w_rf_weight"], 0.0, "0.00%"),
    ]
    for offset, (metric_name, v_gmv, v_tan, v_comp, v_eq, fmt) in enumerate(kpi_data, start=11):
        ws1.cell(row=offset, column=1, value=metric_name).font = bold_font
        for c_i, val in enumerate([v_gmv, v_tan, v_comp, v_eq], start=2):
            cell = ws1.cell(row=offset, column=c_i, value=float(val))
            cell.font = reg_font
            cell.number_format = fmt
        _style_range(ws1, 1, offset, 5, offset, border=thin_border)

    # Asset Allocation Table
    ws1["A18"] = "BẢNG PHÂN BỔ TỶ TRỌNG CHI TIẾT TỪNG TÀI SẢN"
    ws1["A18"].font = sec_font

    alloc_headers = ["Mã Tài sản", "E(Ri) Năm", "Độ lệch chuẩn σi", "Tỷ trọng GMV", "Tỷ trọng Tangency", "Tỷ trọng Complete (y*)", "Tỷ trọng Đều (1/N)"]
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
        _style_range(ws1, 1, r, 7, r, border=thin_border, fill=zebra_fill if i % 2 == 1 else None)

    # Risk-free row & Total row with Excel SUM formula
    rf_row = start_alloc_row + n
    ws1.cell(row=rf_row, column=1, value="CASH / Risk-Free (Rf)").font = bold_font
    ws1.cell(row=rf_row, column=2, value=float(rf)).number_format = "0.00%"
    ws1.cell(row=rf_row, column=3, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=4, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=5, value=0.0).number_format = "0.00%"
    ws1.cell(row=rf_row, column=6, value=float(comp["w_rf_weight"])).number_format = "0.00%"
    ws1.cell(row=rf_row, column=7, value=0.0).number_format = "0.00%"
    _style_range(ws1, 1, rf_row, 7, rf_row, border=thin_border)

    tot_row = rf_row + 1
    ws1.cell(row=tot_row, column=1, value="TỔNG TỶ TRỌNG (SUM)").font = bold_font
    for col_i in range(4, 8):
        col_let = get_column_letter(col_i)
        c = ws1.cell(row=tot_row, column=col_i, value=f"=SUM({col_let}{start_alloc_row}:{col_let}{rf_row})")
        c.font = bold_font
        c.number_format = "0.00%"
    _style_range(ws1, 1, tot_row, 7, tot_row, border=thin_border, fill=accent_fill)

    for col_i in range(1, 8):
        ws1.column_dimensions[get_column_letter(col_i)].width = 24

    # =========================================================================
    # SHEET 2: 02_Asset_Statistics
    # =========================================================================
    ws2 = wb.create_sheet(title="02_Asset_Statistics")
    ws2["A1"] = "THỐNG KÊ TỶ SUẤT SINH LỢI & RỦI RO TỪNG TÀI SẢN (QUY NĂM 252 PHIÊN)"
    ws2["A1"].font = sec_font

    stat_headers = ["STT", "Mã Cổ phiếu", "Thị giá Gần nhất (VNĐ)", "E(Ri) Ngày", "E(Ri) Quy năm (x252)", "Độ lệch chuẩn σi Năm", "Phương sai σi² Năm", "Phần bù Rủi ro E(Ri) - Rf", "Sharpe Đơn lẻ"]
    for col_i, h in enumerate(stat_headers, start=1):
        c = ws2.cell(row=3, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center")

    for i, sym in enumerate(symbols):
        r = 4 + i
        er_y = float(mu[i])
        vol_y = float(std[i])
        var_y = vol_y**2
        p_latest = float(latest_prices.get(sym, 50000.0))

        ws2.cell(row=r, column=1, value=i + 1).alignment = Alignment(horizontal="center")
        ws2.cell(row=r, column=2, value=sym).font = bold_font
        ws2.cell(row=r, column=3, value=p_latest).number_format = "#,##0"
        ws2.cell(row=r, column=4, value=er_y / 252.0).number_format = "0.000%"
        ws2.cell(row=r, column=5, value=er_y).number_format = "0.00%"
        ws2.cell(row=r, column=6, value=vol_y).number_format = "0.00%"
        ws2.cell(row=r, column=7, value=f"=F{r}^2").number_format = "0.0000"
        ws2.cell(row=r, column=8, value=f"=E{r}-{rf}").number_format = "0.00%"
        ws2.cell(row=r, column=9, value=f"=H{r}/F{r}").number_format = "0.000"
        _style_range(ws2, 1, r, 9, r, border=thin_border)

    for col_i in range(1, 10):
        ws2.column_dimensions[get_column_letter(col_i)].width = 22

    # =========================================================================
    # SHEET 3: 03_Covariance_Correlation
    # =========================================================================
    ws3 = wb.create_sheet(title="03_Covariance_Correlation")
    ws3["A1"] = "1. MA TRẬN HIỆP PHƯƠNG SAI QUY NĂM (ANNUALIZED COVARIANCE MATRIX Σ = Σ_daily * 252)"
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
    ws3.cell(row=corr_start - 1, column=1, value="2. MA TRẬN HỆ SỐ TƯƠNG QUAN (CORRELATION MATRIX P)").font = sec_font
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
    # SHEET 4: 04_Matrix_Calculations (Algebraic Step-by-Step)
    # =========================================================================
    ws4 = wb.create_sheet(title="04_Matrix_Calculations")
    ws4["A1"] = "CHI TIẾT GIẢI TÍCH ĐẠI SỐ MA TRẬN MARKOWITZ - MERTON (1972)"
    ws4["A1"].font = sec_font

    ws4["A3"] = "1. MA TRẬN NGHỊCH ĐẢO HIỆP PHƯƠNG SAI (Σ⁻¹ = MINVERSE(Σ))"
    ws4["A3"].font = bold_font

    ws4.cell(row=4, column=1, value="Σ⁻¹").fill = sub_fill
    ws4.cell(row=4, column=1).font = tbl_hdr_font
    for i, sym in enumerate(symbols):
        c_top = ws4.cell(row=4, column=2 + i, value=sym)
        c_top.fill = sub_fill
        c_top.font = tbl_hdr_font
        c_top.alignment = Alignment(horizontal="center")

        r_row = 5 + i
        ws4.cell(row=r_row, column=1, value=sym).font = bold_font
        for j in range(n):
            cell = ws4.cell(row=r_row, column=2 + j, value=float(inv_cov[i][j]))
            cell.number_format = "0.0000"
            cell.font = reg_font
        _style_range(ws4, 1, r_row, n + 1, r_row, border=thin_border)

    sc_start = 5 + n + 2
    ws4.cell(row=sc_start, column=1, value="2. CÁC ĐẠI LƯỢNG VÔ HƯỚNG MERTON (SCALARS A, B, C, D)").font = sec_font
    sc_headers = ["Ký hiệu", "Công thức Đại số Ma trận", "Công thức Excel Tương đương", "Giá trị Tính toán"]
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

    # Vector Z & Analytical Weights Table
    vec_start = sc_start + 8
    ws4.cell(row=vec_start, column=1, value="3. BẢNG TÍNH VECTOR TRUNG GIAN z = Σ⁻¹(μ - Rf·1) VÀ NGHIỆM TỶ TRỌNG").font = sec_font
    vec_headers = ["Mã CP", "μi - Rf", "Vector (Σ⁻¹ · 1)i", "w_GMV Giải tích", "Vector zi = [Σ⁻¹(μ - Rf·1)]i", "w_Tangency Giải tích", "w_Tangency Thực tế (Theo Chế độ)"]
    for col_i, h in enumerate(vec_headers, start=1):
        c = ws4.cell(row=vec_start + 1, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font

    import numpy as np
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
    ws5["A1"] = "TỌA ĐỘ ĐƯỜNG BIÊN HIỆU QUẢ (MARKOWITZ BULLET) & ĐƯỜNG PHÂN BỔ VỐN (CAL)"
    ws5["A1"].font = sec_font

    ef_headers = ["Điểm #", "Độ biến động σp", "Tỷ suất sinh lợi E(Rp)", "Tỷ số Sharpe", "Nhánh Hiệu quả"] + [f"w({s})" for s in symbols]
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

    # Embed OpenPyXL ScatterChart for Efficient Frontier
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
    # SHEET 6: 06_Execution_Order_Sheet (Lot-100 Sizing)
    # =========================================================================
    ws6 = wb.create_sheet(title="06_Execution_Order_Sheet")
    ws6["A1"] = "BẢNG PHÂN BỔ VỐN THỰC TẾ & ĐẶT LỆNH LÔ CHẴN 100 CỔ PHIẾU (HOSE/HNX)"
    ws6["A1"].font = sec_font

    ord_headers = [
        "Mã CP",
        "Thị giá (VNĐ)",
        "Tỷ trọng Tangency (%)",
        "Tỷ trọng Complete y* (%)",
        "Vốn Phân bổ Lý thuyết (VNĐ)",
        "Số lượng CP Chuẩn Lô 100",
        "Giá trị Giải ngân Thực tế (VNĐ)",
        "Tỷ trọng Thực tế (%)",
        "Phí Môi giới Dự kiến (0.15%)",
    ]
    for col_i, h in enumerate(ord_headers, start=1):
        c = ws6.cell(row=3, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font

    total_actual_val = 0.0
    for i, sym in enumerate(symbols):
        r = 4 + i
        price = float(latest_prices.get(sym, 50000.0))
        w_tan_i = float(tan["weights"][i])
        w_comp_i = float(comp["asset_weights"][i])
        ideal_vnd = w_comp_i * nav_vnd
        sign = 1 if ideal_vnd >= 0 else -1
        shares_lot100 = sign * (int(math.floor(abs(ideal_vnd) / (price * 100.0))) * 100)
        actual_vnd = shares_lot100 * price
        total_actual_val += actual_vnd
        fee_vnd = abs(actual_vnd) * 0.0015

        ws6.cell(row=r, column=1, value=sym).font = bold_font
        ws6.cell(row=r, column=2, value=price).number_format = "#,##0"
        ws6.cell(row=r, column=3, value=w_tan_i).number_format = "0.00%"
        ws6.cell(row=r, column=4, value=w_comp_i).number_format = "0.00%"
        ws6.cell(row=r, column=5, value=ideal_vnd).number_format = "#,##0"
        ws6.cell(row=r, column=6, value=shares_lot100).number_format = "#,##0"
        ws6.cell(row=r, column=7, value=f"=B{r}*F{r}").number_format = "#,##0"
        ws6.cell(row=r, column=8, value=f"=G{r}/{nav_vnd}").number_format = "0.00%"
        ws6.cell(row=r, column=9, value=fee_vnd).number_format = "#,##0"
        _style_range(ws6, 1, r, 9, r, border=thin_border)

    cash_r = 4 + n
    residual_cash = nav_vnd - total_actual_val
    ws6.cell(row=cash_r, column=1, value="CASH / Tài sản Phi rủi ro").font = bold_font
    ws6.cell(row=cash_r, column=4, value=float(comp["w_rf_weight"])).number_format = "0.00%"
    ws6.cell(row=cash_r, column=7, value=residual_cash).number_format = "#,##0"
    ws6.cell(row=cash_r, column=8, value=residual_cash / nav_vnd).number_format = "0.00%"
    _style_range(ws6, 1, cash_r, 9, cash_r, border=thin_border, fill=accent_fill)

    for col_i in range(1, 10):
        ws6.column_dimensions[get_column_letter(col_i)].width = 24

    # =========================================================================
    # SHEET 7: 07_Benchmark_Scorecard (Relative Performance Scoreboard)
    # =========================================================================
    bm_data: dict[str, Any] = analysis_data.get("benchmark_comparison", {})
    ws7 = wb.create_sheet(title="07_Benchmark_Scorecard")
    ws7.views.sheetView[0].showGridLines = True

    ws7.merge_cells("A1:D2")
    ws7["A1"] = "BẢNG ĐÁNH GIÁ HIỆU QUẢ TƯƠNG ĐỐI VỚI CHỈ SỐ THỊ TRƯỜNG (BENCHMARK SCORECARD)"
    _style_range(ws7, 1, 1, 4, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    bm_sym = bm_data.get("benchmark_symbol", "VNINDEX")
    bm_name = bm_data.get("benchmark_name", "VN-Index (HOSE Composite)")
    bm_rng = bm_data.get("benchmark_range", "1Y")

    ws7["A4"] = f"CHỈ SỐ THAM CHIẾU: {bm_name} ({bm_sym}) — KHUNG THỜI GIAN SO SÁNH: {bm_rng}"
    ws7["A4"].font = sec_font

    bm_hdrs = ["Chỉ Tiêu Đánh Giá (Metric)", "Danh Mục Tối Ưu (Tangency)", f"Benchmark ({bm_sym})", "Chênh Lệch / Nhận Định"]
    for col_i, h in enumerate(bm_hdrs, start=1):
        c = ws7.cell(row=6, column=col_i, value=h)
        c.fill = sub_fill
        c.font = tbl_hdr_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    p_ret = float(bm_data.get("portfolio_return", tan["expected_return"]))
    b_ret = float(bm_data.get("benchmark_return", 0.115))
    act_ret = float(bm_data.get("active_return", p_ret - b_ret))
    p_vol = float(bm_data.get("portfolio_volatility", tan["volatility"]))
    b_vol = float(bm_data.get("benchmark_volatility", 0.18))
    p_sr = float(bm_data.get("portfolio_sharpe", tan["sharpe_ratio"]))
    b_sr = float(bm_data.get("benchmark_sharpe", 0.40))
    sr_spread = float(bm_data.get("sharpe_spread", p_sr - b_sr))
    beta_val = float(bm_data.get("beta", 1.0))
    alpha_val = float(bm_data.get("jensen_alpha", 0.0))
    te_val = float(bm_data.get("tracking_error", 0.10))
    ir_val = float(bm_data.get("information_ratio", 0.0))
    corr_bm = float(bm_data.get("correlation", 0.75))
    r2_bm = float(bm_data.get("r_squared", corr_bm**2))

    score_rows = [
        ("Lợi suất Kỳ vọng Năm hóa E(R)", p_ret, b_ret, act_ret, "0.00%"),
        ("Độ biến động Năm hóa (Volatility σ)", p_vol, b_vol, p_vol - b_vol, "0.00%"),
        ("Tỷ số Sharpe (Sharpe Ratio)", p_sr, b_sr, sr_spread, "0.000"),
        ("Lợi suất Chủ động (Active Return = Rp - Rm)", act_ret, 0.0, "Outperform" if act_ret >= 0 else "Underperform", "0.00%"),
        ("Jensen's Alpha (α = Rp - [Rf + β(Rm - Rf)])", alpha_val, 0.0, "Tạo Alpha dương" if alpha_val >= 0 else "Alpha âm", "0.00%"),
        ("Hệ số Beta Danh mục (βp)", beta_val, 1.0, "Nhạy hơn thị trường" if beta_val > 1.05 else ("Phòng thủ (< 1)" if beta_val < 0.95 else "Tương đương TT"), "0.000"),
        ("Sai số Bám sát (Tracking Error - TE)", te_val, 0.0, "Rủi ro chủ động", "0.00%"),
        ("Tỷ số Thông tin (Information Ratio - IR)", ir_val, 0.0, "Xuất sắc (> 0.5)" if ir_val >= 0.5 else "Trung bình", "0.000"),
        ("Hệ số Tương quan với Chỉ số (Correlation ρ)", corr_bm, 1.0, f"R² = {r2_bm * 100:.1f}%", "0.000"),
        ("Hệ số Xác định (R-Squared R²)", r2_bm, 1.0, "Mức độ giải thích bởi thị trường", "0.00%"),
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

    # Cumulative Wealth Series (Base = 100)
    cum_block = bm_data.get("cumulative_series", {})
    c_dates = cum_block.get("dates", [])
    c_port = cum_block.get("portfolio_base100", [])
    c_bm = cum_block.get("benchmark_base100", [])

    if c_dates and len(c_dates) == len(c_port) == len(c_bm):
        ws7["A19"] = f"CHUỖI TĂNG TRƯỞNG TÀI SẢN LŨY KẾ (CUMULATIVE WEALTH INDEX - BASE = 100, {len(c_dates)} PHIÊN)"
        ws7["A19"].font = sec_font

        series_hdrs = ["Ngày Giao Dịch (Date)", "Tangency Portfolio (Base=100)", f"{bm_sym} Benchmark (Base=100)", "Chênh Lệch Lũy Kế (Spread)"]
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
    # SHEET 8: 08_Stress_Testing_VaR (Tail Risk & Historical Crisis Scenarios)
    # =========================================================================
    st_data: dict[str, Any] = analysis_data.get("stress_testing", {})
    var_m: dict[str, Any] = st_data.get("var_metrics", {})
    scenarios_list: list[dict[str, Any]] = st_data.get("scenarios", [])

    ws8 = wb.create_sheet(title="08_Stress_Testing_VaR")
    ws8.views.sheetView[0].showGridLines = True

    ws8.merge_cells("A1:H2")
    ws8["A1"] = "BÁO CÁO KIỂM ĐỊNH ÁP LỰC (STRESS TESTING) & QUẢN TRỊ RỦI RO ĐUÔI (VALUE AT RISK / CVaR)"
    _style_range(ws8, 1, 1, 8, 2, font=title_font, fill=navy_fill, align=Alignment(horizontal="center", vertical="center"))

    ws8["A4"] = f"1. CHỈ SỐ RỦI RO ĐUÔI (TAIL-RISK METRICS) — PHƯƠNG PHÁP: {st_data.get('method', 'Historical Simulation')}"
    ws8["A4"].font = sec_font

    var_hdrs = [
        "Chỉ Số Rủi Ro (Risk Metric)",
        "Tỷ Lệ Tổn Thất 1 Ngày (%)",
        "Giá Trị Rủi Ro 1 Ngày (VNĐ)",
        "Tỷ Lệ Tổn Thất 1 Tháng / 21 Phiên (%)",
        "Giá Trị Rủi Ro 1 Tháng / 21 Phiên (VNĐ)",
        "Ý Nghĩa Quản Trị Rủi Ro",
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
            float(var_m.get("var_95_1d_pct", 0.0)),
            float(var_m.get("var_95_1d_vnd", 0.0)),
            float(var_m.get("var_95_21d_pct", 0.0)),
            float(var_m.get("var_95_21d_vnd", 0.0)),
            "Mức lỗ tối đa với độ tin cậy 95% trong điều kiện thị trường bình thường",
        ),
        (
            "Value at Risk (VaR 99%)",
            float(var_m.get("var_99_1d_pct", 0.0)),
            float(var_m.get("var_99_1d_vnd", 0.0)),
            float(var_m.get("var_99_21d_pct", 0.0)),
            float(var_m.get("var_99_21d_vnd", 0.0)),
            "Mức lỗ tối đa với độ tin cậy 99% (chuẩn Basel ủy ban rủi ro)",
        ),
        (
            "Conditional VaR / Expected Shortfall (CVaR 95%)",
            float(var_m.get("cvar_95_1d_pct", 0.0)),
            float(var_m.get("cvar_95_1d_vnd", 0.0)),
            float(var_m.get("cvar_95_21d_pct", 0.0)),
            float(var_m.get("cvar_95_21d_vnd", 0.0)),
            "Tổn thất trung bình kỳ vọng khi thị trường rơi vào vùng 5% xấu nhất",
        ),
        (
            "Conditional VaR / Expected Shortfall (CVaR 99%)",
            float(var_m.get("cvar_99_1d_pct", 0.0)),
            float(var_m.get("cvar_99_1d_vnd", 0.0)),
            float(var_m.get("cvar_99_1d_pct", 0.0)) * math.sqrt(21.0),
            float(var_m.get("cvar_99_1d_vnd", 0.0)) * math.sqrt(21.0),
            "Tổn thất trung bình kỳ vọng khi xảy ra biến cố cực đoan 1% đuôi phân phối",
        ),
    ]

    for idx, (lbl, p1, v1, p21, v21, desc) in enumerate(var_rows, start=7):
        ws8.cell(row=idx, column=1, value=lbl).font = bold_font
        c_p1 = ws8.cell(row=idx, column=2, value=-abs(p1))
        c_p1.number_format = "0.00%"
        c_p1.font = bold_font

        c_v1 = ws8.cell(row=idx, column=3, value=-abs(v1))
        c_v1.number_format = "#,##0"
        c_v1.font = reg_font

        c_p21 = ws8.cell(row=idx, column=4, value=-abs(p21))
        c_p21.number_format = "0.00%"
        c_p21.font = bold_font

        c_v21 = ws8.cell(row=idx, column=5, value=-abs(v21))
        c_v21.number_format = "#,##0"
        c_v21.font = reg_font

        ws8.cell(row=idx, column=6, value=desc).font = reg_font
        _style_range(ws8, 1, idx, 6, idx, border=thin_border, fill=zebra_fill if idx % 2 == 1 else None)

    mdd_comp = float(var_m.get("max_drawdown_complete_pct", 0.0))
    mdd_risky = float(var_m.get("max_drawdown_risky_pct", 0.0))

    ws8.cell(row=11, column=1, value="Maximum Drawdown (Danh mục Tổng thể Complete C)").font = bold_font
    ws8.cell(row=11, column=2, value=-abs(mdd_comp)).number_format = "0.00%"
    ws8.cell(row=11, column=3, value=-abs(mdd_comp * nav_vnd)).number_format = "#,##0"
    ws8.cell(row=11, column=6, value="Mức sụt giảm đỉnh-đáy lớn nhất của Danh mục tổng thể (đã tính đệm Tiền mặt)").font = reg_font
    _style_range(ws8, 1, 11, 6, 11, border=thin_border)

    ws8.cell(row=12, column=1, value="Maximum Drawdown (Danh mục Cổ phiếu Tangency P*)").font = bold_font
    ws8.cell(row=12, column=2, value=-abs(mdd_risky)).number_format = "0.00%"
    ws8.cell(row=12, column=3, value=-abs(mdd_risky * nav_vnd)).number_format = "#,##0"
    ws8.cell(row=12, column=6, value="Mức sụt giảm đỉnh-đáy lớn nhất của rổ 100% cổ phiếu rủi ro").font = reg_font
    _style_range(ws8, 1, 12, 6, 12, border=thin_border, fill=zebra_fill)

    # Historical Crisis Scenarios Table
    ws8["A15"] = "2. KIỂM ĐỊNH SỨC CHỊU ĐỰNG QUA CÁC KỊCH BẢN KHỦNG HOẢNG LỊCH SỬ TTCK VIỆT NAM"
    ws8["A15"].font = sec_font

    sc_hdrs = [
        "Kịch Bản Cú Sốc Lịch Sử (Crisis Scenario)",
        "Giai Đoạn",
        "Cú Sốc Thị Trường (VN-Index)",
        "Tác Động Rổ CP Tangency (%)",
        "Tác Động Danh Mục Tổng Thể C (%)",
        "Tổn Thất Ước Tính (VNĐ)",
        "NAV Còn Lại Sau Cú Sốc (VNĐ)",
        "Giá Trị Đệm Tiền Mặt Bảo Vệ (VNĐ)",
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

        c_ms = ws8.cell(row=s_idx, column=3, value=float(sc.get("market_shock_pct", 0.0)))
        c_ms.number_format = "0.00%"

        c_rk = ws8.cell(row=s_idx, column=4, value=float(sc.get("risky_only_impact_pct", 0.0)))
        c_rk.number_format = "0.00%"

        c_cp = ws8.cell(row=s_idx, column=5, value=float(sc.get("complete_impact_pct", 0.0)))
        c_cp.number_format = "0.00%"
        c_cp.font = bold_font

        c_loss = ws8.cell(row=s_idx, column=6, value=-abs(float(sc.get("estimated_loss_vnd", 0.0))))
        c_loss.number_format = "#,##0"
        c_loss.font = bold_font

        c_post = ws8.cell(row=s_idx, column=7, value=float(sc.get("post_shock_nav_vnd", 0.0)))
        c_post.number_format = "#,##0"

        c_prot = ws8.cell(row=s_idx, column=8, value=float(sc.get("cash_protection_vnd", 0.0)))
        c_prot.number_format = "#,##0"

        _style_range(ws8, 1, s_idx, 8, s_idx, border=thin_border, fill=zebra_fill if s_idx % 2 == 1 else None)

    for col_i, w in enumerate([40, 18, 22, 24, 26, 24, 26, 26], start=1):
        ws8.column_dimensions[get_column_letter(col_i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
