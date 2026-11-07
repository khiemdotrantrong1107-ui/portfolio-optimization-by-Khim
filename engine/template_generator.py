"""
Excel Input Template Generator for Textbook MVO Application.
Uses live market data via `hayinsights_client` and `data_exporter` when available,
or generates a clean structural blank template for manual user entry.
"""
from __future__ import annotations

import io
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from engine import data_exporter, hayinsights_client, textbook_math


def generate_input_template_xlsx(mode: str = "parameters") -> bytes:
    """Create a well-formatted Excel input template using live market data if available."""
    default_syms = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    try:
        live = hayinsights_client.fetch_multi_equity_dataset(
            symbols=default_syms,
            range_str="1y",
            use_adjusted=True,
        )
        moments = textbook_math.compute_moments_from_prices(live["df_prices"], trading_days=252)
        meta = {
            "source": "HayInsights Live API (Finhay / VNSC)",
            "range": live["range"],
            "from_date": live["from_date"],
            "to_date": live["to_date"],
            "formula_version": live["formula_version"],
        }
        if mode == "prices":
            return data_exporter.export_live_price_dataset_xlsx(
                symbols=live["symbols"],
                df_prices=live["df_prices"],
                df_volumes=live.get("df_volumes"),
                daily_returns_df=moments.get("daily_returns_df"),
                latest_prices=live["latest_raw_prices"],
                data_meta=meta,
            )
        else:
            return data_exporter.export_live_parameter_matrix_xlsx(
                symbols=moments["symbols"],
                mu=moments["mu"],
                std=moments["std"],
                corr=moments["corr"],
                cov=moments["cov"],
                latest_prices=live["latest_raw_prices"],
                rf=0.045,
                data_meta=meta,
            )
    except Exception:
        # Clean structural blank template when offline
        wb = Workbook()
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )
        ws = wb.active
        if mode == "prices":
            ws.title = "Historical_Prices"
            headers = ["Date", "TICKER_1", "TICKER_2", "TICKER_3"]
        else:
            ws.title = "Parameters"
            headers = ["Symbol", "Expected_Return", "Std_Dev", "Latest_Price", "TICKER_1", "TICKER_2", "TICKER_3"]

        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = 16

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
