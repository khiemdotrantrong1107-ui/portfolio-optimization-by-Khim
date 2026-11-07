"""
Excel Input Template Generator for Textbook MVO Application.
Generates a clean, ready-to-fill .xlsx file with two sheets:
1. 'Parameters' (Textbook E(R), Std_Dev, and Correlation Matrix)
2. 'Historical_Prices' (252-day daily closing prices)
"""
from __future__ import annotations

import io
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from engine import data_loader


def generate_input_template_xlsx(mode: str = "parameters") -> bytes:
    """Create a well-formatted Excel input template."""
    wb = Workbook()

    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Segoe UI", size=10, color="1E293B")
    note_font = Font(name="Segoe UI", size=9, italic=True, color="475569")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # Sheet 1: Parameters (Textbook Matrix Format)
    ws_param = wb.active
    ws_param.title = "Parameters" if mode == "parameters" else "Manual_Params"

    sample_rows = [
        ("FPT", 0.240, 0.220, [1.00, 0.42, 0.35, 0.38]),
        ("MWG", 0.165, 0.285, [0.42, 1.00, 0.40, 0.46]),
        ("VCB", 0.135, 0.180, [0.35, 0.40, 1.00, 0.32]),
        ("HPG", 0.175, 0.275, [0.38, 0.46, 0.32, 1.00]),
    ]
    headers = ["Symbol", "Expected_Return", "Std_Dev", "FPT", "MWG", "VCB", "HPG"]

    for col_idx, h in enumerate(headers, start=1):
        cell = ws_param.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_param.column_dimensions[get_column_letter(col_idx)].width = 16

    for r_idx, (sym, er, std, corrs) in enumerate(sample_rows, start=2):
        ws_param.cell(row=r_idx, column=1, value=sym).font = Font(name="Segoe UI", size=10, bold=True)
        c_er = ws_param.cell(row=r_idx, column=2, value=er)
        c_er.number_format = "0.00%"
        c_er.font = body_font

        c_std = ws_param.cell(row=r_idx, column=3, value=std)
        c_std.number_format = "0.00%"
        c_std.font = body_font

        for c_i, val in enumerate(corrs, start=4):
            c_corr = ws_param.cell(row=r_idx, column=c_i, value=val)
            c_corr.number_format = "0.00"
            c_corr.font = body_font

        for c_i in range(1, len(headers) + 1):
            ws_param.cell(row=r_idx, column=c_i).border = thin_border

    ws_param.cell(
        row=7,
        column=1,
        value="Hướng dẫn: Nhập mã CP ở cột Symbol, Expected_Return và Std_Dev (dạng thập phân 0.18 hoặc 18%), các cột tiếp theo là Ma trận tương quan đối xứng (đường chéo = 1.00).",
    ).font = note_font

    # Sheet 2: Historical Prices (252 sessions)
    ws_prices = wb.create_sheet(title="Prices" if mode == "prices" else "Historical_Prices")
    df_sample = data_loader.get_market_price_dataframe(["FPT", "MWG", "VCB", "HPG"], n_sessions=60)

    price_headers = ["Date"] + list(df_sample.columns)
    for col_idx, h in enumerate(price_headers, start=1):
        cell = ws_prices.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        ws_prices.column_dimensions[get_column_letter(col_idx)].width = 15

    for r_idx, (dt, row_vals) in enumerate(df_sample.iterrows(), start=2):
        c_dt = ws_prices.cell(row=r_idx, column=1, value=dt.strftime("%Y-%m-%d"))
        c_dt.font = body_font
        c_dt.border = thin_border
        for c_i, sym in enumerate(df_sample.columns, start=2):
            c_p = ws_prices.cell(row=r_idx, column=c_i, value=float(row_vals[sym]))
            c_p.number_format = "#,##0"
            c_p.font = body_font
            c_p.border = thin_border

    # Put the requested mode sheet first
    if mode == "prices":
        wb._sheets = [ws_prices, ws_param]

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
