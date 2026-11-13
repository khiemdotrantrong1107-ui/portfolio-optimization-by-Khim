"""
HayInsights (Finhay / VNSC) Live Market Data Connector & Vietnam Equity Directory
for Textbook MVO Workbench.
Fetches real-time & historical daily prices (both raw Close and dividend-adjusted Close)
from https://api-v2.hayinsights.com/openapi/v1/market/vn/equities/{symbol}/prices
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE_URL = "https://api-v2.hayinsights.com/openapi/v1"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Simple in-memory TTL cache to avoid redundant API hits during slider adjustments & Excel exports
_PRICE_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

# Comprehensive directory of 150+ liquid Vietnamese equities across HOSE, HNX, UPCoM
VN_TICKER_DIRECTORY: list[dict[str, str]] = [
    # --- NGÂN HÀNG (BANKING) ---
    {"symbol": "VCB", "name": "Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "BID", "name": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam (BIDV)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "CTG", "name": "Ngân hàng TMCP Công Thương Việt Nam (VietinBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "TCB", "name": "Ngân hàng TMCP Kỹ Thương Việt Nam (Techcombank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "MBB", "name": "Ngân hàng TMCP Quân Đội (MBBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "ACB", "name": "Ngân hàng TMCP Á Châu (ACB)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "VPB", "name": "Ngân hàng TMCP Việt Nam Thịnh Vượng (VPBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "STB", "name": "Ngân hàng TMCP Sài Gòn Thương Tín (Sacombank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "HDB", "name": "Ngân hàng TMCP Phát triển TP.HCM (HDBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "VIB", "name": "Ngân hàng TMCP Quốc Tế Việt Nam (VIB)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "TPB", "name": "Ngân hàng TMCP Tiên Phong (TPBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "SHB", "name": "Ngân hàng TMCP Sài Gòn - Hà Nội (SHB)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "SSB", "name": "Ngân hàng TMCP Đông Nam Á (SeABank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN30"},
    {"symbol": "LPB", "name": "Ngân hàng TMCP Lộc Phát Việt Nam (LPBank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN100"},
    {"symbol": "MSB", "name": "Ngân hàng TMCP Hàng Hải Việt Nam (MSB)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN100"},
    {"symbol": "OCB", "name": "Ngân hàng TMCP Phương Đông (OCB)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN100"},
    {"symbol": "EIB", "name": "Ngân hàng TMCP Xuất Nhập Khẩu Việt Nam (Eximbank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "VN100"},
    {"symbol": "NAB", "name": "Ngân hàng TMCP Nam Á (Nam A Bank)", "exchange": "HOSE", "sector": "Ngân hàng", "group": "HOSE"},
    {"symbol": "ABB", "name": "Ngân hàng TMCP An Bình (ABBank)", "exchange": "UPCoM", "sector": "Ngân hàng", "group": "UPCoM"},
    {"symbol": "BAB", "name": "Ngân hàng TMCP Bắc Á (Bac A Bank)", "exchange": "HNX", "sector": "Ngân hàng", "group": "HNX"},
    {"symbol": "NVB", "name": "Ngân hàng TMCP Quốc Dân (NCB)", "exchange": "HNX", "sector": "Ngân hàng", "group": "HNX"},

    # --- CHỨNG KHOÁN (SECURITIES / BROKERAGE) ---
    {"symbol": "SSI", "name": "CTCP Chứng khoán SSI", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN30"},
    {"symbol": "VND", "name": "CTCP Chứng khoán VNDIRECT", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "VCI", "name": "CTCP Chứng khoán Vietcap", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "HCM", "name": "CTCP Chứng khoán TP.HCM (HSC)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "VIX", "name": "CTCP Chứng khoán VIX", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "FTS", "name": "CTCP Chứng khoán FPT (FPTS)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "BSI", "name": "CTCP Chứng khoán BIDV (BSC)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "VN100"},
    {"symbol": "CTS", "name": "CTCP Chứng khoán Ngân hàng Công Thương (VietinBankSc)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "HOSE"},
    {"symbol": "AGR", "name": "CTCP Chứng khoán Agribank (Agriseco)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "HOSE"},
    {"symbol": "ORS", "name": "CTCP Chứng khoán Tiên Phong (TPS)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "HOSE"},
    {"symbol": "VDS", "name": "CTCP Chứng khoán Rồng Việt (VDSC)", "exchange": "HOSE", "sector": "Chứng khoán", "group": "HOSE"},
    {"symbol": "SHS", "name": "CTCP Chứng khoán Sài Gòn - Hà Nội (SHS)", "exchange": "HNX", "sector": "Chứng khoán", "group": "HNX30"},
    {"symbol": "MBS", "name": "CTCP Chứng khoán MB (MBS)", "exchange": "HNX", "sector": "Chứng khoán", "group": "HNX30"},
    {"symbol": "BVS", "name": "CTCP Chứng khoán Bảo Việt (BVSC)", "exchange": "HNX", "sector": "Chứng khoán", "group": "HNX"},

    # --- CÔNG NGHỆ & VIỄN THÔNG (TECHNOLOGY & TELECOM) ---
    {"symbol": "FPT", "name": "CTCP FPT (FPT Corp)", "exchange": "HOSE", "sector": "Công nghệ", "group": "VN30"},
    {"symbol": "CMG", "name": "CTCP Tập đoàn Công nghệ CMC", "exchange": "HOSE", "sector": "Công nghệ", "group": "VN100"},
    {"symbol": "ELC", "name": "CTCP Công nghệ - Viễn thông ELCOM", "exchange": "HOSE", "sector": "Công nghệ", "group": "HOSE"},
    {"symbol": "ITD", "name": "CTCP Công nghệ Tiên Phong", "exchange": "HOSE", "sector": "Công nghệ", "group": "HOSE"},
    {"symbol": "CTR", "name": "Tổng Công ty CP Công trình Viettel (Viettel Construction)", "exchange": "HOSE", "sector": "Viễn thông & Hạ tầng", "group": "VN100"},
    {"symbol": "VGI", "name": "Tổng Công ty CP Đầu tư Quốc tế Viettel (Viettel Global)", "exchange": "UPCoM", "sector": "Viễn thông", "group": "UPCoM"},
    {"symbol": "FOX", "name": "CTCP Viễn thông FPT (FPT Telecom)", "exchange": "UPCoM", "sector": "Viễn thông", "group": "UPCoM"},
    {"symbol": "FOC", "name": "CTCP Dịch vụ Trực tuyến FPT (FPT Online)", "exchange": "UPCoM", "sector": "Công nghệ", "group": "UPCoM"},

    # --- BÁN LẺ & TIÊU DÙNG (RETAIL & CONSUMER) ---
    {"symbol": "MWG", "name": "CTCP Đầu tư Thế Giới Di Động", "exchange": "HOSE", "sector": "Bán lẻ", "group": "VN30"},
    {"symbol": "PNJ", "name": "CTCP Vàng bạc Đá quý Phú Nhuận", "exchange": "HOSE", "sector": "Bán lẻ", "group": "VN100"},
    {"symbol": "FRT", "name": "CTCP Bán lẻ Kỹ thuật số FPT (FPT Retail)", "exchange": "HOSE", "sector": "Bán lẻ", "group": "VN100"},
    {"symbol": "DGW", "name": "CTCP Thế Giới Số (Digiworld)", "exchange": "HOSE", "sector": "Bán lẻ", "group": "VN100"},
    {"symbol": "PET", "name": "Tổng Công ty CP Dịch vụ Tổng hợp Dầu khí (Petrosetco)", "exchange": "HOSE", "sector": "Bán lẻ", "group": "HOSE"},
    {"symbol": "VNM", "name": "CTCP Sữa Việt Nam (Vinamilk)", "exchange": "HOSE", "sector": "Tiêu dùng & Thực phẩm", "group": "VN30"},
    {"symbol": "MSN", "name": "CTCP Tập đoàn Masan (Masan Group)", "exchange": "HOSE", "sector": "Tiêu dùng & Thực phẩm", "group": "VN30"},
    {"symbol": "SAB", "name": "Tổng CTCP Bia - Rượu - Nước giải khát Sài Gòn (Sabeco)", "exchange": "HOSE", "sector": "Tiêu dùng & Đồ uống", "group": "VN30"},
    {"symbol": "MCH", "name": "CTCP Hàng tiêu dùng Masan (Masan Consumer)", "exchange": "UPCoM", "sector": "Tiêu dùng & Thực phẩm", "group": "UPCoM"},
    {"symbol": "QNS", "name": "CTCP Đường Quảng Ngãi", "exchange": "UPCoM", "sector": "Tiêu dùng & Thực phẩm", "group": "UPCoM"},
    {"symbol": "KDC", "name": "CTCP Tập đoàn KIDO", "exchange": "HOSE", "sector": "Tiêu dùng & Thực phẩm", "group": "VN100"},
    {"symbol": "SBT", "name": "CTCP Thành Thành Công - Biên Hòa (TTC AgriS)", "exchange": "HOSE", "sector": "Tiêu dùng & Nông nghiệp", "group": "VN100"},

    # --- THÉP & VẬT LIỆU XÂY DỰNG (STEEL & MATERIALS) ---
    {"symbol": "HPG", "name": "CTCP Tập đoàn Hòa Phát", "exchange": "HOSE", "sector": "Thép & Vật liệu", "group": "VN30"},
    {"symbol": "HSG", "name": "CTCP Tập đoàn Hoa Sen", "exchange": "HOSE", "sector": "Thép & Vật liệu", "group": "VN100"},
    {"symbol": "NKG", "name": "CTCP Thép Nam Kim", "exchange": "HOSE", "sector": "Thép & Vật liệu", "group": "VN100"},
    {"symbol": "TLH", "name": "CTCP Tập đoàn Thép Tiến Lên", "exchange": "HOSE", "sector": "Thép & Vật liệu", "group": "HOSE"},
    {"symbol": "SMC", "name": "CTCP Đầu tư Thương mại SMC", "exchange": "HOSE", "sector": "Thép & Vật liệu", "group": "HOSE"},
    {"symbol": "TVN", "name": "Tổng Công ty Thép Việt Nam (VNSteel)", "exchange": "UPCoM", "sector": "Thép & Vật liệu", "group": "UPCoM"},
    {"symbol": "BMP", "name": "CTCP Nhựa Bình Minh", "exchange": "HOSE", "sector": "Vật liệu xây dựng", "group": "VN100"},
    {"symbol": "NTP", "name": "CTCP Nhựa Thiếu niên Tiền Phong", "exchange": "HNX", "sector": "Vật liệu xây dựng", "group": "HNX30"},
    {"symbol": "VCS", "name": "CTCP Vicostone", "exchange": "HNX", "sector": "Vật liệu xây dựng", "group": "HNX30"},
    {"symbol": "HT1", "name": "CTCP Xi măng Hà Tiên 1", "exchange": "HOSE", "sector": "Vật liệu xây dựng", "group": "HOSE"},
    {"symbol": "PTB", "name": "CTCP Phú Tài", "exchange": "HOSE", "sector": "Gỗ & Đá ốp lát", "group": "HOSE"},
    {"symbol": "KSB", "name": "CTCP Khoáng sản và Xây dựng Bình Dương", "exchange": "HOSE", "sector": "Đá & Vật liệu", "group": "HOSE"},

    # --- HÓA CHẤT, PHÂN BÓN & CAO SU (CHEMICALS, FERTILIZER & RUBBER) ---
    {"symbol": "DGC", "name": "CTCP Tập đoàn Hóa chất Đức Giang", "exchange": "HOSE", "sector": "Hóa chất", "group": "VN100"},
    {"symbol": "CSV", "name": "CTCP Hóa chất Cơ bản Miền Nam", "exchange": "HOSE", "sector": "Hóa chất", "group": "HOSE"},
    {"symbol": "DPM", "name": "Tổng Công ty Phân bón và Hóa chất Dầu khí (Đạm Phú Mỹ)", "exchange": "HOSE", "sector": "Phân bón & Hóa chất", "group": "VN100"},
    {"symbol": "DCM", "name": "CTCP Phân bón Dầu khí Cà Mau (Đạm Cà Mau)", "exchange": "HOSE", "sector": "Phân bón & Hóa chất", "group": "VN100"},
    {"symbol": "BFC", "name": "CTCP Phân bón Bình Điền", "exchange": "HOSE", "sector": "Phân bón", "group": "HOSE"},
    {"symbol": "LAS", "name": "CTCP Supe Phốt phát và Hóa chất Lâm Thao", "exchange": "HNX", "sector": "Phân bón & Hóa chất", "group": "HNX30"},
    {"symbol": "GVR", "name": "Tập đoàn Công nghiệp Cao su Việt Nam", "exchange": "HOSE", "sector": "Cao su & KCN", "group": "VN30"},
    {"symbol": "PHR", "name": "CTCP Cao su Phước Hòa", "exchange": "HOSE", "sector": "Cao su & KCN", "group": "VN100"},
    {"symbol": "DPR", "name": "CTCP Cao su Đồng Phú", "exchange": "HOSE", "sector": "Cao su & KCN", "group": "HOSE"},
    {"symbol": "DRC", "name": "CTCP Cao su Đà Nẵng", "exchange": "HOSE", "sector": "Cao su & Săm lốp", "group": "VN100"},

    # --- BẤT ĐỘNG SẢN DÂN DỤNG & THƯƠNG MẠI (REAL ESTATE) ---
    {"symbol": "VHM", "name": "CTCP Vinhomes", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN30"},
    {"symbol": "VIC", "name": "Tập đoàn Vingroup - CTCP", "exchange": "HOSE", "sector": "Tập đoàn đa ngành", "group": "VN30"},
    {"symbol": "VRE", "name": "CTCP Vincom Retail", "exchange": "HOSE", "sector": "Bất động sản bán lẻ", "group": "VN30"},
    {"symbol": "KDH", "name": "CTCP Đầu tư và Kinh doanh Nhà Khang Điền", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "NLG", "name": "CTCP Đầu tư Nam Long", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "DXG", "name": "CTCP Tập đoàn Đất Xanh", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "DIG", "name": "Tổng CTCP Đầu tư Phát triển Xây dựng (DIC Corp)", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "PDR", "name": "CTCP Phát triển Bất động sản Phát Đạt", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "NVL", "name": "CTCP Tập đoàn Đầu tư Địa ốc No Va (Novaland)", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "HDG", "name": "CTCP Tập đoàn Hà Đô", "exchange": "HOSE", "sector": "Bất động sản & Điện", "group": "VN100"},
    {"symbol": "TCH", "name": "CTCP Đầu tư Dịch vụ Tài chính Hoàng Huy", "exchange": "HOSE", "sector": "Bất động sản", "group": "VN100"},
    {"symbol": "HDC", "name": "CTCP Phát triển Nhà Bà Rịa - Vũng Tàu (Hodeco)", "exchange": "HOSE", "sector": "Bất động sản", "group": "HOSE"},
    {"symbol": "NTL", "name": "CTCP Phát triển Đô thị Từ Liêm (Lideco)", "exchange": "HOSE", "sector": "Bất động sản", "group": "HOSE"},
    {"symbol": "CEO", "name": "CTCP Tập đoàn C.E.O", "exchange": "HNX", "sector": "Bất động sản", "group": "HNX30"},

    # --- BẤT ĐỘNG SẢN KHU CÔNG NGHIỆP (INDUSTRIAL PARKS) ---
    {"symbol": "BCM", "name": "Tổng Công ty Đầu tư và Phát triển Công nghiệp (Becamex IDC)", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "VN30"},
    {"symbol": "KBC", "name": "Tổng Công ty Phát triển Đô thị Kinh Bắc", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "VN100"},
    {"symbol": "VGC", "name": "Tổng Công ty Viglacera - CTCP", "exchange": "HOSE", "sector": "Khu công nghiệp & VLXD", "group": "VN100"},
    {"symbol": "SZC", "name": "CTCP Sonadezi Châu Đức", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "VN100"},
    {"symbol": "SIP", "name": "CTCP Đầu tư Sài Gòn VRG", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "VN100"},
    {"symbol": "IDC", "name": "Tổng Công ty IDICO - CTCP", "exchange": "HNX", "sector": "Khu công nghiệp", "group": "HNX30"},
    {"symbol": "LHG", "name": "CTCP Long Hậu", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "HOSE"},
    {"symbol": "ITA", "name": "CTCP Đầu tư và Công nghiệp Tân Tạo", "exchange": "HOSE", "sector": "Khu công nghiệp", "group": "HOSE"},

    # --- DẦU KHÍ & NĂNG LƯỢNG ĐIỆN (OIL, GAS & POWER UTILITIES) ---
    {"symbol": "GAS", "name": "Tổng Công ty Khí Việt Nam - CTCP (PV GAS)", "exchange": "HOSE", "sector": "Dầu khí & Khí đốt", "group": "VN30"},
    {"symbol": "PLX", "name": "Tập đoàn Xăng dầu Việt Nam (Petrolimex)", "exchange": "HOSE", "sector": "Xăng dầu", "group": "VN30"},
    {"symbol": "PVD", "name": "Tổng CTCP Khoan và Dịch vụ Khoan Dầu khí (PV Drilling)", "exchange": "HOSE", "sector": "Dầu khí", "group": "VN100"},
    {"symbol": "PVT", "name": "Tổng CTCP Vận tải Dầu khí (PVTrans)", "exchange": "HOSE", "sector": "Vận tải Dầu khí", "group": "VN100"},
    {"symbol": "PVS", "name": "Tổng CTCP Dịch vụ Kỹ thuật Dầu khí Việt Nam (PTSC)", "exchange": "HNX", "sector": "Dầu khí", "group": "HNX30"},
    {"symbol": "BSR", "name": "CTCP Lọc Hóa dầu Bình Sơn", "exchange": "UPCoM", "sector": "Lọc hóa dầu", "group": "UPCoM"},
    {"symbol": "OIL", "name": "Tổng Công ty Dầu Việt Nam - CTCP (PVOIL)", "exchange": "UPCoM", "sector": "Xăng dầu", "group": "UPCoM"},
    {"symbol": "PVC", "name": "Tổng Công ty Hóa chất và Dịch vụ Dầu khí (PVChem)", "exchange": "HNX", "sector": "Dầu khí", "group": "HNX30"},
    {"symbol": "POW", "name": "Tổng Công ty Điện lực Dầu khí Việt Nam (PV Power)", "exchange": "HOSE", "sector": "Điện & Năng lượng", "group": "VN30"},
    {"symbol": "REE", "name": "CTCP Cơ Điện Lạnh (REE Corp)", "exchange": "HOSE", "sector": "Năng lượng & Hạ tầng", "group": "VN100"},
    {"symbol": "PC1", "name": "CTCP Tập đoàn PC1", "exchange": "HOSE", "sector": "Điện & Xây lắp", "group": "VN100"},
    {"symbol": "NT2", "name": "CTCP Điện lực Dầu khí Nhơn Trạch 2", "exchange": "HOSE", "sector": "Điện & Năng lượng", "group": "HOSE"},
    {"symbol": "GEG", "name": "CTCP Điện Gia Lai", "exchange": "HOSE", "sector": "Điện tái tạo", "group": "HOSE"},
    {"symbol": "BCG", "name": "CTCP Tập đoàn Bamboo Capital", "exchange": "HOSE", "sector": "Năng lượng & BĐS", "group": "VN100"},
    {"symbol": "TV2", "name": "CTCP Tư vấn Xây dựng Điện 2 (PECC2)", "exchange": "HOSE", "sector": "Tư vấn Điện", "group": "HOSE"},

    # --- CẢNG BIỂN, VẬN TẢI & HÀNG KHÔNG (PORTS, LOGISTICS & AVIATION) ---
    {"symbol": "GMD", "name": "CTCP Gemadept", "exchange": "HOSE", "sector": "Cảng & Logistics", "group": "VN100"},
    {"symbol": "HAH", "name": "CTCP Vận tải và Xếp dỡ Hải An", "exchange": "HOSE", "sector": "Vận tải biển", "group": "VN100"},
    {"symbol": "VSC", "name": "CTCP Tập đoàn Container Việt Nam (Viconship)", "exchange": "HOSE", "sector": "Cảng & Logistics", "group": "VN100"},
    {"symbol": "VOS", "name": "CTCP Vận tải Biển Việt Nam (Vosco)", "exchange": "HOSE", "sector": "Vận tải biển", "group": "HOSE"},
    {"symbol": "VTP", "name": "Tổng Công ty CP Bưu chính Viettel (Viettel Post)", "exchange": "HOSE", "sector": "Bưu chính & Logistics", "group": "VN100"},
    {"symbol": "TMS", "name": "CTCP Transimex", "exchange": "HOSE", "sector": "Logistics", "group": "HOSE"},
    {"symbol": "PHP", "name": "CTCP Cảng Hải Phòng", "exchange": "HNX", "sector": "Cảng biển", "group": "HNX"},
    {"symbol": "SGP", "name": "CTCP Cảng Sài Gòn", "exchange": "UPCoM", "sector": "Cảng biển", "group": "UPCoM"},
    {"symbol": "VJC", "name": "CTCP Hàng không VietJet (Vietjet Air)", "exchange": "HOSE", "sector": "Hàng không", "group": "VN30"},
    {"symbol": "HVN", "name": "Tổng Công ty Hàng không Việt Nam (Vietnam Airlines)", "exchange": "HOSE", "sector": "Hàng không", "group": "HOSE"},
    {"symbol": "ACV", "name": "Tổng Công ty Cảng Hàng không Việt Nam (ACV)", "exchange": "UPCoM", "sector": "Hạ tầng Sân bay", "group": "UPCoM"},
    {"symbol": "SCS", "name": "CTCP Dịch vụ Hàng hóa Sài Gòn (SCSC)", "exchange": "HOSE", "sector": "Hàng hóa Hàng không", "group": "HOSE"},

    # --- XÂY DỰNG & ĐẦU TƯ CÔNG (CONSTRUCTION & INFRASTRUCTURE) ---
    {"symbol": "CTD", "name": "CTCP Xây dựng Coteccons", "exchange": "HOSE", "sector": "Xây dựng", "group": "VN100"},
    {"symbol": "VCG", "name": "Tổng CTCP Xuất nhập khẩu và Xây dựng Việt Nam (Vinaconex)", "exchange": "HOSE", "sector": "Xây dựng & Đầu tư công", "group": "VN100"},
    {"symbol": "HHV", "name": "CTCP Đầu tư Hạ tầng Giao thông Đèo Cả", "exchange": "HOSE", "sector": "Đầu tư công & Hạ tầng", "group": "VN100"},
    {"symbol": "LCG", "name": "CTCP Lizen", "exchange": "HOSE", "sector": "Đầu tư công", "group": "HOSE"},
    {"symbol": "FCN", "name": "CTCP FECON", "exchange": "HOSE", "sector": "Xây dựng & Hạ tầng", "group": "HOSE"},
    {"symbol": "CII", "name": "CTCP Đầu tư Hạ tầng Kỹ thuật TP.HCM", "exchange": "HOSE", "sector": "Hạ tầng & BĐS", "group": "VN100"},
    {"symbol": "HBC", "name": "CTCP Tập đoàn Xây dựng Hòa Bình", "exchange": "UPCoM", "sector": "Xây dựng", "group": "UPCoM"},
    {"symbol": "DPG", "name": "CTCP Tập đoàn Đạt Phương", "exchange": "HOSE", "sector": "Xây dựng & BĐS", "group": "HOSE"},

    # --- THỦY SẢN, NÔNG NGHIỆP & DỆT MAY (SEAFOOD, AGRICULTURE & TEXTILES) ---
    {"symbol": "VHC", "name": "CTCP Vĩnh Hoàn", "exchange": "HOSE", "sector": "Thủy sản", "group": "VN100"},
    {"symbol": "ANV", "name": "CTCP Nam Việt (Navico)", "exchange": "HOSE", "sector": "Thủy sản", "group": "VN100"},
    {"symbol": "IDI", "name": "CTCP Đầu tư và Phát triển Đa Quốc Gia I.D.I", "exchange": "HOSE", "sector": "Thủy sản", "group": "HOSE"},
    {"symbol": "FMC", "name": "CTCP Thực phẩm Sao Ta (Fimex VN)", "exchange": "HOSE", "sector": "Thủy sản", "group": "HOSE"},
    {"symbol": "MPC", "name": "CTCP Tập đoàn Thủy sản Minh Phú", "exchange": "UPCoM", "sector": "Thủy sản", "group": "UPCoM"},
    {"symbol": "DBC", "name": "CTCP Tập đoàn Dabaco Việt Nam", "exchange": "HOSE", "sector": "Nông nghiệp & Chăn nuôi", "group": "VN100"},
    {"symbol": "BAF", "name": "CTCP Nông nghiệp BAF Việt Nam", "exchange": "HOSE", "sector": "Nông nghiệp & Chăn nuôi", "group": "HOSE"},
    {"symbol": "HAG", "name": "CTCP Hoàng Anh Gia Lai", "exchange": "HOSE", "sector": "Nông nghiệp", "group": "HOSE"},
    {"symbol": "PAN", "name": "CTCP Tập đoàn PAN (The PAN Group)", "exchange": "HOSE", "sector": "Nông nghiệp & Thực phẩm", "group": "VN100"},
    {"symbol": "LTG", "name": "CTCP Tập đoàn Lộc Trời", "exchange": "UPCoM", "sector": "Nông nghiệp", "group": "UPCoM"},
    {"symbol": "TNG", "name": "CTCP Đầu tư và Thương mại TNG", "exchange": "HNX", "sector": "Dệt may", "group": "HNX30"},
    {"symbol": "MSH", "name": "CTCP May Sông Hồng", "exchange": "HOSE", "sector": "Dệt may", "group": "HOSE"},
    {"symbol": "VGT", "name": "Tập đoàn Dệt May Việt Nam (Vinatex)", "exchange": "UPCoM", "sector": "Dệt may", "group": "UPCoM"},
    {"symbol": "STK", "name": "CTCP Sợi Thế Kỷ", "exchange": "HOSE", "sector": "Dệt may", "group": "HOSE"},
    {"symbol": "GIL", "name": "CTCP Sản xuất Kinh doanh Xuất nhập khẩu Bình Thạnh (Gilimex)", "exchange": "HOSE", "sector": "Dệt may & KCN", "group": "HOSE"},

    # --- DƯỢC PHẨM, BẢO HIỂM & KHÁC (PHARMA, INSURANCE & OTHERS) ---
    {"symbol": "DHG", "name": "CTCP Dược Hậu Giang", "exchange": "HOSE", "sector": "Dược phẩm", "group": "HOSE"},
    {"symbol": "IMP", "name": "CTCP Dược phẩm Imexpharm", "exchange": "HOSE", "sector": "Dược phẩm", "group": "HOSE"},
    {"symbol": "DBD", "name": "CTCP Dược - Trang thiết bị Y tế Bình Định (Bidiphar)", "exchange": "HOSE", "sector": "Dược phẩm", "group": "HOSE"},
    {"symbol": "TRA", "name": "CTCP Traphaco", "exchange": "HOSE", "sector": "Dược phẩm", "group": "HOSE"},
    {"symbol": "BVH", "name": "Tập đoàn Bảo Việt", "exchange": "HOSE", "sector": "Bảo hiểm", "group": "VN30"},
    {"symbol": "MIG", "name": "Tổng CTCP Bảo hiểm Quân Đội (MIC)", "exchange": "HOSE", "sector": "Bảo hiểm", "group": "HOSE"},
    {"symbol": "BMI", "name": "Tổng CTCP Bảo Minh", "exchange": "HOSE", "sector": "Bảo hiểm", "group": "HOSE"},
    {"symbol": "PVI", "name": "CTCP PVI", "exchange": "HNX", "sector": "Bảo hiểm", "group": "HNX30"},
    {"symbol": "GEX", "name": "CTCP Tập đoàn GELEX", "exchange": "HOSE", "sector": "Thiết bị điện & KCN", "group": "VN100"},
    {"symbol": "SAM", "name": "CTCP SAM Holdings", "exchange": "HOSE", "sector": "Đầu tư đa ngành", "group": "HOSE"},
]

_DIRECTORY_BY_SYMBOL = {item["symbol"]: item for item in VN_TICKER_DIRECTORY}


def search_tickers(query: str = "", limit: int = 30) -> list[dict[str, str]]:
    """
    Search tickers by prefix (1-2+ characters), substring in symbol, company name, or sector.
    Prioritizes:
      1. Exact symbol match
      2. Symbol starts with query (e.g., typing 'V' or 'VC' puts VCB, VCI, VCG, VCS at the top)
      3. Symbol contains query
      4. Company name or sector contains query
    Also supports arbitrary 3-letter custom tickers not in the static list.
    """
    q = (query or "").strip()
    if not q:
        # Return VN30 and top popular equities when search box is empty/focused
        return VN_TICKER_DIRECTORY[:limit]

    q_up = q.upper()
    q_low = q.lower()

    tier_exact: list[dict[str, str]] = []
    tier_prefix: list[dict[str, str]] = []
    tier_sym_sub: list[dict[str, str]] = []
    tier_meta_sub: list[dict[str, str]] = []

    for item in VN_TICKER_DIRECTORY:
        sym = item["symbol"]
        if sym == q_up:
            tier_exact.append(item)
        elif sym.startswith(q_up):
            tier_prefix.append(item)
        elif q_up in sym:
            tier_sym_sub.append(item)
        elif (
            q_low in item["name"].lower()
            or q_low in item["sector"].lower()
            or q_low in item["exchange"].lower()
            or q_low in item["group"].lower()
        ):
            tier_meta_sub.append(item)

    combined = tier_exact + tier_prefix + tier_sym_sub + tier_meta_sub

    # If user typed a valid 3-4 character stock code that isn't in static directory, offer direct HayInsights lookup
    if 2 <= len(q_up) <= 4 and q_up.isalnum() and q_up not in _DIRECTORY_BY_SYMBOL:
        combined.append(
            {
                "symbol": q_up,
                "name": f"Tra cứu trực tiếp mã '{q_up}' từ HayInsights API",
                "exchange": "HOSE/HNX/UPCoM",
                "sector": "Mã tùy chỉnh (Live API)",
                "group": "Custom",
            }
        )

    return combined[:limit]


def load_api_key() -> str:
    """Load HAYINSIGHTS_API_KEY from environment or local .env file."""
    key = os.environ.get("HAYINSIGHTS_API_KEY", "").strip()
    if key:
        return key

    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "HAYINSIGHTS_API_KEY":
                val = v.strip().strip('"').strip("'")
                os.environ["HAYINSIGHTS_API_KEY"] = val
                return val
    return ""


def fetch_single_equity(symbol: str, range_str: str = "1y", api_key: str | None = None) -> dict[str, Any]:
    """
    Fetch historical daily price series for a single Vietnamese equity (HOSE/HNX/UPCoM).
    Uses in-memory caching for speed and rate-limit protection.
    HayInsights API natively accepts: 5d, 1m, 3m, 6m, 1y, 3y, 5y, max.
    """
    sym = symbol.strip().upper()
    rng_raw = (range_str or "1y").strip().lower()
    # Map 2y -> 3y and ytd -> 1y for upstream API query; slicing is handled downstream
    api_rng_map = {
        "2y": "3y",
        "ytd": "1y",
    }
    api_rng = api_rng_map.get(rng_raw, rng_raw)
    if api_rng not in ("5d", "1m", "3m", "6m", "1y", "3y", "5y", "max"):
        api_rng = "1y"

    cache_key = (sym, api_rng)

    now = time.time()
    if cache_key in _PRICE_CACHE:
        ts, cached_payload = _PRICE_CACHE[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return cached_payload

    key = (api_key or load_api_key()).strip()
    if not key:
        raise ValueError("Chưa cấu hình HAYINSIGHTS_API_KEY trong biến môi trường hoặc file .env.")

    url = f"{BASE_URL}/market/vn/equities/{urllib.parse.quote(sym)}/prices?range={urllib.parse.quote(api_rng)}"
    req = urllib.request.Request(
        url,
        headers={
            "X-API-Key": key,
            "Accept": "application/json",
            "User-Agent": "TextbookMVO-Workbench/2.4",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            pass
        raise ValueError(f"HayInsights API lỗi ({e.code}) với mã '{sym}': {err_body or e.reason}") from e
    except Exception as e:
        raise ValueError(f"Không thể kết nối HayInsights API cho mã '{sym}': {e}") from e

    data_block = payload.get("data", {})
    points = data_block.get("points", [])
    if not points or len(points) < 5:
        raise ValueError(f"Mã '{sym}' không có đủ dữ liệu lịch sử trên HayInsights (nhận được {len(points)} phiên).")

    _PRICE_CACHE[cache_key] = (now, payload)
    return payload


def validate_and_quote_ticker(symbol: str, api_key: str | None = None) -> dict[str, Any]:
    """
    Verify a ticker symbol against HayInsights API and return its latest price, date, and directory metadata.
    """
    sym = symbol.strip().upper()
    payload = fetch_single_equity(sym, range_str="1m", api_key=api_key)
    points = payload["data"]["points"]
    last_pt = points[-1]
    meta = _DIRECTORY_BY_SYMBOL.get(
        sym,
        {
            "symbol": sym,
            "name": f"Cổ phiếu {sym}",
            "exchange": "VN Market",
            "sector": "Cổ phiếu niêm yết",
            "group": "Live",
        },
    )
    return {
        "valid": True,
        "symbol": sym,
        "name": meta["name"],
        "exchange": meta["exchange"],
        "sector": meta["sector"],
        "latest_price": float(last_pt.get("close", 0.0)),
        "adjusted_close": float(last_pt.get("adjustedClose", last_pt.get("close", 0.0))),
        "latest_date": str(last_pt.get("date", "")),
        "volume": int(last_pt.get("volume", 0)),
    }


def fetch_multi_equity_dataset(
    symbols: list[str],
    range_str: str = "1y",
    use_adjusted: bool = True,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Fetch multiple equities concurrently from HayInsights API, align trading dates,
    and return aligned DataFrames for prices, trading volumes, raw close prices, and
    latest unadjusted closing prices (for HOSE/HNX order lot sizing).
    Never silently deduplicates repeated tickers or fills missing prices with zero-return rows.
    """
    clean_syms: list[str] = []
    seen_syms: set[str] = set()
    duplicate_syms: list[str] = []
    for s in symbols:
        s_up = str(s).strip().upper()
        if not s_up:
            continue
        if s_up in seen_syms:
            if s_up not in duplicate_syms:
                duplicate_syms.append(s_up)
        else:
            seen_syms.add(s_up)
            clean_syms.append(s_up)

    if duplicate_syms:
        raise ValueError(
            f"Danh sách mã cổ phiếu bị trùng lặp: {', '.join(duplicate_syms)}. Vui lòng loại bỏ mã trùng."
        )

    if len(clean_syms) < 2:
        raise ValueError("Vui lòng chọn hoặc nhập ít nhất 2 mã cổ phiếu hợp lệ để tối ưu hóa danh mục.")

    rng_req = (range_str or "1y").strip().lower()
    fetched_at = datetime.now().isoformat(timespec="seconds")
    results: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=min(8, len(clean_syms))) as pool:
        future_map = {
            pool.submit(fetch_single_equity, sym, rng_req, api_key): sym
            for sym in clean_syms
        }
        for fut in as_completed(future_map):
            sym = future_map[fut]
            try:
                results[sym] = fut.result()
            except Exception as exc:
                errors.append(str(exc))

    if errors:
        raise ValueError(" | ".join(errors))

    adj_series_list = []
    raw_series_list = []
    vol_series_list = []
    latest_raw_prices: dict[str, float] = {}
    latest_price_dates: dict[str, str] = {}
    raw_session_counts: dict[str, int] = {}

    for sym in clean_syms:
        payload = results[sym]
        points = payload["data"]["points"]
        df_sym = pd.DataFrame(points)
        if "date" not in df_sym.columns or "close" not in df_sym.columns:
            raise ValueError(f"Dữ liệu giá của mã '{sym}' thiếu cột 'date' hoặc 'close'.")
        df_sym["date"] = pd.to_datetime(df_sym["date"], errors="coerce")
        if df_sym["date"].isna().any():
            raise ValueError(f"Mã '{sym}' có ngày giao dịch không hợp lệ trong chuỗi giá.")
        df_sym = df_sym.sort_values("date").drop_duplicates(subset=["date"], keep="last")

        price_col = "adjustedClose" if (use_adjusted and "adjustedClose" in df_sym.columns) else "close"
        df_sym[price_col] = pd.to_numeric(df_sym[price_col], errors="coerce")
        df_sym["close"] = pd.to_numeric(df_sym["close"], errors="coerce")
        if "volume" in df_sym.columns:
            df_sym["volume"] = pd.to_numeric(df_sym["volume"], errors="coerce").fillna(0.0)
        else:
            df_sym["volume"] = 0.0

        invalid_mask = (
            (~np.isfinite(df_sym[price_col].to_numpy(dtype=float)))
            | (~np.isfinite(df_sym["close"].to_numpy(dtype=float)))
            | (df_sym[price_col] <= 0)
            | (df_sym["close"] <= 0)
        )
        if invalid_mask.any():
            raise ValueError(
                f"Mã '{sym}' có {int(invalid_mask.sum())} phiên chứa giá <= 0 hoặc NaN/Inf ở cột {price_col}/close."
            )

        df_sym = df_sym.set_index("date")
        raw_session_counts[sym] = int(len(df_sym))
        latest_raw_prices[sym] = float(df_sym["close"].iloc[-1])
        latest_price_dates[sym] = str(df_sym.index[-1].date())

        adj_series_list.append(df_sym[price_col].rename(sym))
        raw_series_list.append(df_sym["close"].rename(sym))
        vol_series_list.append(df_sym["volume"].rename(sym))

    union_idx = adj_series_list[0].index
    for s_idx in adj_series_list[1:]:
        union_idx = union_idx.union(s_idx.index)
    union_idx = union_idx.sort_values()

    df_aligned = pd.concat(adj_series_list, axis=1, join="inner").dropna(how="any").sort_index()
    df_raw_aligned = pd.concat(raw_series_list, axis=1, join="inner").reindex(df_aligned.index)
    df_vol_aligned = pd.concat(vol_series_list, axis=1, join="inner").reindex(df_aligned.index).fillna(0.0)

    # Apply calendar window slicing for derived ranges ('2y' or 'ytd')
    union_idx_window = union_idx
    if len(df_aligned) > 10:
        last_dt = df_aligned.index[-1]
        if rng_req == "2y":
            cutoff = last_dt - pd.Timedelta(days=730)
            sliced = df_aligned[df_aligned.index >= cutoff]
            if len(sliced) >= 10:
                df_aligned = sliced
                df_raw_aligned = df_raw_aligned.reindex(df_aligned.index)
                df_vol_aligned = df_vol_aligned.reindex(df_aligned.index)
                union_idx_window = union_idx[union_idx >= cutoff]
        elif rng_req == "ytd":
            cutoff = pd.Timestamp(year=last_dt.year, month=1, day=1)
            sliced = df_aligned[df_aligned.index >= cutoff]
            if len(sliced) >= 10:
                df_aligned = sliced
                df_raw_aligned = df_raw_aligned.reindex(df_aligned.index)
                df_vol_aligned = df_vol_aligned.reindex(df_aligned.index)
                union_idx_window = union_idx[union_idx >= cutoff]

    if len(df_aligned) < 10:
        raise ValueError(
            f"Số phiên giao dịch trùng khớp giữa các mã ({', '.join(clean_syms)}) quá ít ({len(df_aligned)} phiên)."
        )

    dropped_days_count = max(0, int(len(union_idx_window) - len(df_aligned)))

    df_aligned.index.name = "Date"
    df_raw_aligned.index.name = "Date"
    df_vol_aligned.index.name = "Date"

    from_date = str(df_aligned.index[0].date())
    to_date = str(df_aligned.index[-1].date())

    return {
        "symbols": clean_syms,
        "df_prices": df_aligned,
        "df_raw_prices": df_raw_aligned,
        "df_volumes": df_vol_aligned,
        "latest_raw_prices": latest_raw_prices,
        "latest_price_dates": latest_price_dates,
        "raw_session_counts": raw_session_counts,
        "aligned_price_sessions": int(len(df_aligned)),
        "aligned_sessions": int(len(df_aligned) - 1),
        "dropped_days_count": dropped_days_count,
        "fetched_at": fetched_at,
        "price_basis": "adjustedClose" if use_adjusted else "close",
        "from_date": from_date,
        "to_date": to_date,
        "sessions_count": int(len(df_aligned) - 1),
        "range": rng_req,
        "use_adjusted": use_adjusted,
        "formula_version": "vnsc-adjusted-close-v1" if use_adjusted else "raw-close",
    }
