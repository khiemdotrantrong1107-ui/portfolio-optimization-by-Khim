"""
Local SQLite Quantitative Database & Zero-Quota Cache Manager
for Portfolio Optimization by Khim (v2.4 Institutional Edition).

Provides:
1. Relational ANSI SQL Schema V2.1 across 7 tables + 1 system log table + 3 analytical views.
2. High-concurrency SQLite connection pool using Write-Ahead Logging (WAL mode) and busy_timeout.
3. Seeding of 159 Vietnamese equities, benchmark market indices, and FRED-standard macro indicators.
4. Corporate Action Drift Detection to prevent artificial price cliffs during dividend distributions.
5. Point-in-Time financial ratio snapshots and zero-quota time-series retrieval for MVO calculations.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "hayinsights_quant.sqlite3"
SAMPLE_EXCEL_PATH = PROJECT_ROOT / "sample_data" / "VN_Bluechips_5Assets_Historical_Prices.xlsx"

# ---------------------------------------------------------------------------
# Database Connection Helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Establish an optimized SQLite connection with WAL journal mode,
    foreign key enforcement, and a 5-second busy timeout for concurrent safety.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


# ---------------------------------------------------------------------------
# DDL Schema V2.1 Initialization
# ---------------------------------------------------------------------------

SCHEMA_DDL = """
-- ============================================================================
-- TẦNG 1: DIMENSION TABLES (DANH MỤC THỰC THỂ GỐC)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dim_equities (
    symbol              VARCHAR(10) PRIMARY KEY,
    code                VARCHAR(10) NOT NULL,
    name_local          VARCHAR(150) NOT NULL,
    name_en             VARCHAR(150),
    exchange            VARCHAR(10) NOT NULL,
    market_group        VARCHAR(20),
    currency            VARCHAR(5) DEFAULT 'VND',
    sector_code         VARCHAR(50),
    sector_name         VARCHAR(100),
    sector_standard     VARCHAR(20) DEFAULT 'ICB',
    trading_unit        INTEGER DEFAULT 100,
    shares_outstanding  BIGINT,
    treasury_shares     BIGINT DEFAULT 0,
    market_cap          NUMERIC(22, 2),
    formula_version     VARCHAR(60),
    is_active           INTEGER DEFAULT 1,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_market_indices (
    index_code          VARCHAR(15) PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    exchange            VARCHAR(10) NOT NULL,
    currency            VARCHAR(5) DEFAULT 'VND',
    description         VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS dim_macro_indicators (
    indicator_code      VARCHAR(40) PRIMARY KEY,
    category            VARCHAR(25) NOT NULL,
    country             VARCHAR(5) NOT NULL,
    tenor               VARCHAR(10),
    frequency           VARCHAR(15) NOT NULL,
    name_vn             VARCHAR(150) NOT NULL,
    unit                VARCHAR(20) NOT NULL,
    source_endpoint     VARCHAR(120)
);

-- ============================================================================
-- TẦNG 2: FACT TABLES (DỮ LIỆU CHUỖI THỜI GIAN & ĐỊNH LƯỢNG)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_equity_daily_prices (
    symbol              VARCHAR(10) NOT NULL,
    trading_date        DATE NOT NULL,
    open_price          NUMERIC(18, 4),
    high_price          NUMERIC(18, 4),
    low_price           NUMERIC(18, 4),
    close_price         NUMERIC(18, 4) NOT NULL,
    adjusted_close      NUMERIC(18, 4) NOT NULL,
    volume              BIGINT DEFAULT 0,
    adjusted_volume     BIGINT DEFAULT 0,
    trading_value       NUMERIC(22, 2) DEFAULT 0.0,
    is_partial          INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trading_date),
    FOREIGN KEY (symbol) REFERENCES dim_equities(symbol) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_eq_prices_sym_date_desc ON fact_equity_daily_prices(symbol, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_eq_prices_date ON fact_equity_daily_prices(trading_date);

CREATE TABLE IF NOT EXISTS fact_market_indices_daily (
    index_code          VARCHAR(15) NOT NULL,
    trading_date        DATE NOT NULL,
    open_point          NUMERIC(18, 4),
    high_point          NUMERIC(18, 4),
    low_point           NUMERIC(18, 4),
    close_point         NUMERIC(18, 4) NOT NULL,
    change_point        NUMERIC(18, 4),
    change_pct          NUMERIC(10, 4),
    total_volume        BIGINT DEFAULT 0,
    total_value         NUMERIC(22, 2) DEFAULT 0.0,
    advances            INTEGER DEFAULT 0,
    declines            INTEGER DEFAULT 0,
    no_change           INTEGER DEFAULT 0,
    foreign_buy_value   NUMERIC(22, 2) DEFAULT 0.0,
    foreign_sell_value  NUMERIC(22, 2) DEFAULT 0.0,
    foreign_net_value   NUMERIC(22, 2) DEFAULT 0.0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, trading_date),
    FOREIGN KEY (index_code) REFERENCES dim_market_indices(index_code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_idx_daily_code_date_desc ON fact_market_indices_daily(index_code, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_idx_daily_date ON fact_market_indices_daily(trading_date);

CREATE TABLE IF NOT EXISTS fact_macro_time_series (
    indicator_code      VARCHAR(40) NOT NULL,
    record_date         DATE NOT NULL,
    published_date      DATE,
    period_label        VARCHAR(20),
    value               NUMERIC(18, 6) NOT NULL,
    bid_value           NUMERIC(18, 6),
    ask_value           NUMERIC(18, 6),
    previous_value      NUMERIC(18, 6),
    forecast_value      NUMERIC(18, 6),
    change_value        NUMERIC(18, 6),
    change_pct          NUMERIC(10, 4),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (indicator_code, record_date),
    FOREIGN KEY (indicator_code) REFERENCES dim_macro_indicators(indicator_code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_macro_ind_date_desc ON fact_macro_time_series(indicator_code, record_date DESC);
CREATE INDEX IF NOT EXISTS idx_macro_date ON fact_macro_time_series(record_date);

CREATE TABLE IF NOT EXISTS fact_equity_financial_ratios (
    symbol              VARCHAR(10) NOT NULL,
    as_of_date          DATE NOT NULL,
    fiscal_period       VARCHAR(20) NOT NULL,
    period_end_date     DATE,
    published_date      DATE,
    pe_ratio            NUMERIC(12, 4),
    pb_ratio            NUMERIC(12, 4),
    roe                 NUMERIC(12, 4),
    roa                 NUMERIC(12, 4),
    eps                 NUMERIC(18, 2),
    market_cap          NUMERIC(22, 2),
    high_52w            NUMERIC(18, 4),
    low_52w             NUMERIC(18, 4),
    change_1d_pct       NUMERIC(10, 4),
    change_3m_pct       NUMERIC(10, 4),
    change_6m_pct       NUMERIC(10, 4),
    ytd_change_pct      NUMERIC(10, 4),
    change_1y_pct       NUMERIC(10, 4),
    change_3y_pct       NUMERIC(10, 4),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, as_of_date),
    FOREIGN KEY (symbol) REFERENCES dim_equities(symbol) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ratios_sym_date_desc ON fact_equity_financial_ratios(symbol, as_of_date DESC);

-- ============================================================================
-- TẦNG 3: SYSTEM LOGS (QUẢN TRỊ ĐỒNG BỘ & BẢO VỆ HẠN NGẠCH API)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sys_sync_logs (
    resource_id             VARCHAR(40) NOT NULL,
    sync_scope              VARCHAR(25) NOT NULL,
    last_synced_date        DATE,
    records_upserted        INTEGER DEFAULT 0,
    http_status             INTEGER DEFAULT 200,
    rate_limit_remaining    INTEGER,
    rate_limit_weight_used  INTEGER,
    rate_limit_reset_at     TIMESTAMP,
    last_sync_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (resource_id, sync_scope)
);

-- ============================================================================
-- TẦNG 4: ANALYTICAL VIEWS (BẢNG ẢO TRỰC QUAN CHO DBEAVER & QUANT ENGINE)
-- ============================================================================

DROP VIEW IF EXISTS vw_equity_master_dashboard;
CREATE VIEW vw_equity_master_dashboard AS
SELECT 
    e.symbol,
    e.name_local,
    e.exchange,
    e.market_group,
    e.sector_name,
    p.trading_date AS latest_date,
    p.close_price,
    p.adjusted_close,
    p.volume,
    ROUND((p.trading_value * 1.0) / 1e9, 2) AS trading_value_billion_vnd,
    r.fiscal_period,
    r.period_end_date,
    r.pe_ratio,
    r.pb_ratio,
    r.roe,
    r.roa,
    r.eps,
    ROUND(( COALESCE(e.market_cap, r.market_cap, 0.0) * 1.0 ) / 1e12, 2) AS market_cap_trillion_vnd
FROM dim_equities e
LEFT JOIN fact_equity_daily_prices p 
    ON e.symbol = p.symbol 
    AND p.trading_date = (SELECT MAX(trading_date) FROM fact_equity_daily_prices WHERE symbol = e.symbol)
LEFT JOIN fact_equity_financial_ratios r 
    ON e.symbol = r.symbol 
    AND r.as_of_date = (SELECT MAX(as_of_date) FROM fact_equity_financial_ratios WHERE symbol = e.symbol);

DROP VIEW IF EXISTS vw_equity_daily_returns;
CREATE VIEW vw_equity_daily_returns AS
SELECT 
    symbol,
    trading_date,
    close_price,
    adjusted_close,
    LAG(adjusted_close, 1) OVER (PARTITION BY symbol ORDER BY trading_date) AS prev_adjusted_close,
    ROUND(
        ((adjusted_close * 1.0) - LAG(adjusted_close * 1.0, 1) OVER (PARTITION BY symbol ORDER BY trading_date))
        / NULLIF(LAG(adjusted_close * 1.0, 1) OVER (PARTITION BY symbol ORDER BY trading_date), 0.0),
        6
    ) AS simple_return,
    volume,
    trading_value
FROM fact_equity_daily_prices;

DROP VIEW IF EXISTS vw_macro_latest_snapshot;
CREATE VIEW vw_macro_latest_snapshot AS
SELECT
    m.indicator_code,
    m.category,
    m.country,
    m.tenor,
    m.frequency,
    m.name_vn,
    s.record_date AS latest_date,
    s.period_label,
    s.value,
    m.unit,
    s.previous_value,
    s.forecast_value,
    s.change_value,
    s.change_pct
FROM dim_macro_indicators m
LEFT JOIN fact_macro_time_series s
    ON m.indicator_code = s.indicator_code
    AND s.record_date = (SELECT MAX(record_date) FROM fact_macro_time_series WHERE indicator_code = m.indicator_code);
"""


def init_db() -> None:
    """Initialize database tables, indexes, and views."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_DDL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Seeding Utilities (Zero Quota Ingestion)
# ---------------------------------------------------------------------------

def seed_initial_data() -> dict[str, int]:
    """
    Seed initial reference directory and baseline time series into local SQLite:
    1. 159 Vietnamese equities from directory
    2. 4 market indices (VNINDEX, VN30, HNX, UPCOM)
    3. 12 FRED-standard macro indicators + baseline snapshots
    4. 5 core assets (FPT, MWG, VCB, HPG, VNM) from local sample Excel if available.
    """
    init_db()
    conn = get_connection()
    stats = {"equities": 0, "indices": 0, "macro_indicators": 0}

    try:
        # 1. Seed Dim Equities
        from engine.hayinsights_client import VN_TICKER_DIRECTORY
        for item in VN_TICKER_DIRECTORY:
            conn.execute(
                """
                INSERT INTO dim_equities (symbol, code, name_local, exchange, market_group, sector_name, trading_unit, currency)
                VALUES (?, ?, ?, ?, ?, ?, 100, 'VND')
                ON CONFLICT(symbol) DO UPDATE SET
                    name_local = excluded.name_local,
                    exchange = excluded.exchange,
                    market_group = excluded.market_group,
                    sector_name = excluded.sector_name;
                """,
                (item["symbol"], item["symbol"], item["name"], item["exchange"], item.get("group", "HOSE"), item.get("sector", "Khác"))
            )
            stats["equities"] += 1

        # 2. Seed Dim Market Indices
        indices_data = [
            ("VNINDEX", "Chỉ số VN-Index (HOSE Composite)", "HOSE", "VND", "Chỉ số đại diện toàn thị trường HOSE"),
            ("VN30", "Chỉ số VN30 (Large-Cap Bluechips)", "HOSE", "VND", "Top 30 cổ phiếu vốn hóa và thanh khoản lớn nhất"),
            ("HNX", "Chỉ số HNX-Index", "HNX", "VND", "Chỉ số toàn thị trường Sở GDCK Hà Nội"),
            ("UPCOM", "Chỉ số UPCoM-Index", "UPCoM", "VND", "Chỉ số thị trường đăng ký giao dịch công ty đại chúng"),
        ]
        for idx in indices_data:
            conn.execute(
                """
                INSERT INTO dim_market_indices (index_code, name, exchange, currency, description)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(index_code) DO UPDATE SET
                    name = excluded.name,
                    exchange = excluded.exchange,
                    description = excluded.description;
                """,
                idx
            )
            stats["indices"] += 1

        # 3. Seed Dim Macro Indicators & Baseline Snapshots
        macro_indicators = [
            ("VN_BOND_1Y", "GOV_BOND_YIELD", "VN", "1Y", "DAILY", "Lợi suất Trái phiếu Chính phủ Việt Nam 1Y", "%", "/macro/monetary-policy/rates-yields"),
            ("VN_BOND_2Y", "GOV_BOND_YIELD", "VN", "2Y", "DAILY", "Lợi suất Trái phiếu Chính phủ Việt Nam 2Y", "%", "/macro/monetary-policy/rates-yields"),
            ("VN_BOND_5Y", "GOV_BOND_YIELD", "VN", "5Y", "DAILY", "Lợi suất Trái phiếu Chính phủ Việt Nam 5Y", "%", "/macro/monetary-policy/rates-yields"),
            ("VN_BOND_10Y", "GOV_BOND_YIELD", "VN", "10Y", "DAILY", "Lợi suất Trái phiếu Chính phủ Việt Nam 10Y (Rf chuẩn)", "%", "/macro/monetary-policy/rates-yields"),
            ("US_BOND_10Y", "GOV_BOND_YIELD", "US", "10Y", "DAILY", "Lợi suất Kho bạc Mỹ 10Y (US 10Y Treasury)", "%", "/macro/monetary-policy/rates-yields"),
            ("JP_BOND_10Y", "GOV_BOND_YIELD", "JP", "10Y", "DAILY", "Lợi suất Trái phiếu Chính phủ Nhật Bản 10Y (JGB 10Y)", "%", "/macro/monetary-policy/rates-yields"),
            ("VN_POLICY_RATE", "POLICY_RATE", "VN", None, "MONTHLY", "Lãi suất Tái cấp vốn Ngân hàng Nhà nước (SBV Refinancing Rate)", "%", "/macro/monetary-policy/rates-yields"),
            ("FX_USD_VND", "FX_RATE", "VN", None, "DAILY", "Tỷ giá Giao ngay USD/VND", "VND", "/macro/exchange-rate"),
            ("FX_USD_JPY", "FX_RATE", "JP", None, "DAILY", "Tỷ giá USD/JPY", "JPY", "/macro/exchange-rate"),
            ("FX_DXY", "FX_RATE", "GLOBAL", None, "DAILY", "Chỉ số Sức mạnh Đồng Đô la Mỹ (US Dollar Index)", "INDEX_PTS", "/macro/exchange-rate"),
            ("VN_GDP_YOY", "MACRO_ECON", "VN", None, "QUARTERLY", "Tăng trưởng GDP Việt Nam (YoY)", "%", "/macro/indicators"),
            ("VN_CPI_YOY", "MACRO_ECON", "VN", None, "MONTHLY", "Chỉ số Lạm phát CPI Việt Nam (YoY)", "%", "/macro/indicators"),
        ]
        for m in macro_indicators:
            conn.execute(
                """
                INSERT INTO dim_macro_indicators (indicator_code, category, country, tenor, frequency, name_vn, unit, source_endpoint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    name_vn = excluded.name_vn,
                    unit = excluded.unit;
                """,
                m
            )
            stats["macro_indicators"] += 1

        conn.commit()
    finally:
        conn.close()

    return stats


# ---------------------------------------------------------------------------
# Core Ingestion & Drift-Check Functions
# ---------------------------------------------------------------------------

def upsert_equity_prices_with_drift_check(
    symbol: str,
    points: list[dict[str, Any]],
    formula_version: str = "vnsc-adjusted-close-v1",
) -> dict[str, Any]:
    """
    Insert or update daily price points with Corporate Action Drift Check.
    If at the latest overlap trading date between incoming points and existing DB records,
    the relative difference of adjustedClose > 0.01% (0.0001), drift_detected is True,
    signaling the caller to refetch full history to prevent price cliff artifacts.
    """
    sym = symbol.strip().upper()
    if not points:
        return {"records_upserted": 0, "drift_detected": False, "overlap_dates": 0}

    conn = get_connection()
    drift_detected = False
    overlap_count = 0

    try:
        # Check existing records for overlap
        dates_in_points = [p.get("date") for p in points if p.get("date")]
        if dates_in_points:
            placeholders = ",".join(["?"] * len(dates_in_points))
            cur = conn.execute(
                f"SELECT trading_date, adjusted_close FROM fact_equity_daily_prices WHERE symbol = ? AND trading_date IN ({placeholders}) ORDER BY trading_date DESC",
                [sym] + dates_in_points
            )
            db_overlap = {row["trading_date"]: float(row["adjusted_close"]) for row in cur.fetchall()}
            overlap_count = len(db_overlap)

            for p in sorted(points, key=lambda x: str(x.get("date", "")), reverse=True):
                p_date = str(p.get("date", ""))
                if p_date in db_overlap:
                    api_adj = float(p.get("adjustedClose", p.get("close", 0.0)))
                    db_adj = db_overlap[p_date]
                    if db_adj > 1e-6:
                        rel_diff = abs(api_adj - db_adj) / db_adj
                        if rel_diff > 0.0001:  # > 0.01% drift detected
                            drift_detected = True
                            break

        rows_to_insert = []
        for p in points:
            p_date = str(p.get("date", "")).strip()
            if not p_date:
                continue
            raw_close = float(p.get("close", 0.0))
            adj_close = float(p.get("adjustedClose", raw_close))
            vol = int(p.get("volume", 0))
            adj_vol = int(p.get("adjustedVolume", vol))
            tr_val = float(p.get("tradingValue", raw_close * vol))
            o_price = float(p["open"]) if ("open" in p and p["open"] is not None) else None
            h_price = float(p["high"]) if ("high" in p and p["high"] is not None) else None
            l_price = float(p["low"]) if ("low" in p and p["low"] is not None) else None
            is_part = 1 if p.get("isPartial") else 0

            rows_to_insert.append((sym, p_date, o_price, h_price, l_price, raw_close, adj_close, vol, adj_vol, tr_val, is_part))

        conn.executemany(
            """
            INSERT INTO fact_equity_daily_prices
            (symbol, trading_date, open_price, high_price, low_price, close_price, adjusted_close, volume, adjusted_volume, trading_value, is_partial)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trading_date) DO UPDATE SET
                open_price = COALESCE(excluded.open_price, fact_equity_daily_prices.open_price),
                high_price = COALESCE(excluded.high_price, fact_equity_daily_prices.high_price),
                low_price = COALESCE(excluded.low_price, fact_equity_daily_prices.low_price),
                close_price = excluded.close_price,
                adjusted_close = excluded.adjusted_close,
                volume = excluded.volume,
                adjusted_volume = excluded.adjusted_volume,
                trading_value = excluded.trading_value,
                is_partial = excluded.is_partial;
            """,
            rows_to_insert
        )

        # Update formula version on dim_equities
        conn.execute(
            "UPDATE dim_equities SET formula_version = ?, updated_at = CURRENT_TIMESTAMP WHERE symbol = ?",
            (formula_version, sym)
        )

        conn.commit()
    finally:
        conn.close()

    return {
        "records_upserted": len(rows_to_insert),
        "drift_detected": drift_detected,
        "overlap_dates": overlap_count,
    }


def upsert_equity_master_and_ratios(symbol: str, payload: dict[str, Any], headers: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Ingest Endpoint 1 payload (GET /openapi/v1/market/vn/equities/{symbol}) into
    dim_equities and fact_equity_financial_ratios.
    """
    sym = symbol.strip().upper()
    data = payload.get("data", {})
    if not data or data.get("symbol", "").upper() != sym:
        return {"status": "error", "message": "Invalid equity master payload"}

    conn = get_connection()
    try:
        code = str(data.get("code", sym))
        name_local = str(data.get("nameLocal", data.get("name", f"Cổ phiếu {sym}")))
        name_en = str(data.get("name", name_local))
        exchange = str(data.get("exchange", "HOSE"))
        currency = str(data.get("currency", "VND"))

        sector = data.get("sector") or {}
        sector_code = sector.get("code")
        sector_name = sector.get("name")
        sector_std = sector.get("classification", "ICB")

        overview = data.get("overview") or {}
        tr_unit = int(overview.get("tradingUnit", 100))
        shares_out = overview.get("sharesOutstanding")
        treasury_sh = overview.get("treasuryShares") or 0
        market_cap = overview.get("marketCap")

        meta = payload.get("meta") or {}
        formula_ver = meta.get("formula_version")

        conn.execute(
            """
            INSERT INTO dim_equities 
            (symbol, code, name_local, name_en, exchange, currency, sector_code, sector_name, sector_standard, trading_unit, shares_outstanding, treasury_shares, market_cap, formula_version, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                code = excluded.code,
                name_local = excluded.name_local,
                name_en = excluded.name_en,
                exchange = excluded.exchange,
                sector_code = COALESCE(excluded.sector_code, dim_equities.sector_code),
                sector_name = COALESCE(excluded.sector_name, dim_equities.sector_name),
                trading_unit = excluded.trading_unit,
                shares_outstanding = COALESCE(excluded.shares_outstanding, dim_equities.shares_outstanding),
                treasury_shares = COALESCE(excluded.treasury_shares, dim_equities.treasury_shares),
                market_cap = COALESCE(excluded.market_cap, dim_equities.market_cap),
                formula_version = COALESCE(excluded.formula_version, dim_equities.formula_version),
                updated_at = CURRENT_TIMESTAMP;
            """,
            (sym, code, name_local, name_en, exchange, currency, sector_code, sector_name, sector_std, tr_unit, shares_out, treasury_sh, market_cap, formula_ver)
        )

        # Ingest Ratios
        ratios = data.get("ratios") or {}
        basis = ratios.get("basis") or {}
        fiscal_period = str(basis.get("fiscalPeriod") or "Latest")
        period_end = basis.get("periodEnd")
        as_of = str(meta.get("as_of") or data.get("quote", {}).get("tradingDate") or date.today().isoformat())

        pe = ratios.get("peRatio")
        pb = ratios.get("pbRatio")
        roe = ratios.get("roe")
        roa = ratios.get("roa")
        eps = ratios.get("eps")

        range52w = data.get("range52w") or {}
        high52 = range52w.get("high")
        low52 = range52w.get("low")

        p_changes = data.get("periodChanges") or {}
        c1d = p_changes.get("change1d")
        c3m = p_changes.get("change3m")
        c6m = p_changes.get("change6m")
        cytd = p_changes.get("ytdChange")
        c1y = p_changes.get("change12m")
        c3y = p_changes.get("change3y")

        conn.execute(
            """
            INSERT INTO fact_equity_financial_ratios
            (symbol, as_of_date, fiscal_period, period_end_date, published_date, pe_ratio, pb_ratio, roe, roa, eps, market_cap, high_52w, low_52w, change_1d_pct, change_3m_pct, change_6m_pct, ytd_change_pct, change_1y_pct, change_3y_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, as_of_date) DO UPDATE SET
                fiscal_period = excluded.fiscal_period,
                period_end_date = excluded.period_end_date,
                pe_ratio = excluded.pe_ratio,
                pb_ratio = excluded.pb_ratio,
                roe = excluded.roe,
                roa = excluded.roa,
                eps = excluded.eps,
                market_cap = excluded.market_cap,
                high_52w = excluded.high_52w,
                low_52w = excluded.low_52w,
                change_1d_pct = excluded.change_1d_pct,
                change_3m_pct = excluded.change_3m_pct,
                change_6m_pct = excluded.change_6m_pct,
                ytd_change_pct = excluded.ytd_change_pct,
                change_1y_pct = excluded.change_1y_pct,
                change_3y_pct = excluded.change_3y_pct;
            """,
            (sym, as_of, fiscal_period, period_end, as_of, pe, pb, roe, roa, eps, market_cap, high52, low52, c1d, c3m, c6m, cytd, c1y, c3y)
        )

        if headers:
            record_sync_log(sym, "EQUITY_MASTER", as_of, 1, headers)

        conn.commit()
    finally:
        conn.close()

    return {"status": "success", "symbol": sym}


def record_sync_log(
    resource_id: str,
    sync_scope: str,
    last_synced_date: str | None,
    records_upserted: int,
    headers: dict[str, Any] | None = None,
    http_status: int = 200,
) -> None:
    """Record rate-limit quota and execution timestamp into sys_sync_logs."""
    conn = get_connection()
    try:
        rem = None
        weight = None
        reset_ts = None
        if headers:
            for k, v in headers.items():
                kl = str(k).lower()
                if "remaining" in kl:
                    try:
                        rem = int(v)
                    except Exception:
                        pass
                elif "weight-used" in kl or "weight" in kl:
                    try:
                        weight = int(v)
                    except Exception:
                        pass
                elif "reset" in kl:
                    try:
                        reset_ts = datetime.fromtimestamp(int(v)).isoformat()
                    except Exception:
                        pass

        conn.execute(
            """
            INSERT INTO sys_sync_logs 
            (resource_id, sync_scope, last_synced_date, records_upserted, http_status, rate_limit_remaining, rate_limit_weight_used, rate_limit_reset_at, last_sync_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(resource_id, sync_scope) DO UPDATE SET
                last_synced_date = excluded.last_synced_date,
                records_upserted = excluded.records_upserted,
                http_status = excluded.http_status,
                rate_limit_remaining = COALESCE(excluded.rate_limit_remaining, sys_sync_logs.rate_limit_remaining),
                rate_limit_weight_used = COALESCE(excluded.rate_limit_weight_used, sys_sync_logs.rate_limit_weight_used),
                rate_limit_reset_at = COALESCE(excluded.rate_limit_reset_at, sys_sync_logs.rate_limit_reset_at),
                last_sync_at = CURRENT_TIMESTAMP;
            """,
            (resource_id, sync_scope, last_synced_date, records_upserted, http_status, rem, weight, reset_ts)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# High-Performance Retrieval Utilities
# ---------------------------------------------------------------------------

def get_single_equity_cached_payload(symbol: str, range_str: str = "1y") -> dict[str, Any] | None:
    """
    Check if local DB has fresh historical prices for symbol.
    Returns simulated HayInsights JSON payload format if adequate data exists.
    """
    sym = symbol.strip().upper()
    range_days_map = {
        "5d": 10,
        "1m": 35,
        "3m": 95,
        "6m": 190,
        "1y": 380,
        "2y": 750,
        "3y": 1120,
        "5y": 1850,
        "max": 3650,
    }
    lookback = range_days_map.get(range_str.lower(), 380)

    min_sessions_map = {
        "5d": 3,
        "1m": 15,
        "3m": 45,
        "6m": 90,
        "1y": 200,
        "2y": 400,
        "3y": 600,
        "5y": 1000,
        "max": 100,
    }
    min_required = min_sessions_map.get(range_str.lower(), 15)

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT trading_date, open_price, high_price, low_price, close_price, adjusted_close, volume, adjusted_volume, trading_value, is_partial
            FROM fact_equity_daily_prices
            WHERE symbol = ?
            ORDER BY trading_date DESC
            LIMIT ?
            """,
            (sym, lookback)
        )
        rows = cur.fetchall()
        if not rows or len(rows) < min_required:
            return None

        # Check freshness: latest date should be within recent trading days
        latest_date_str = rows[0]["trading_date"]
        latest_dt = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
        today = date.today()
        # If latest session is older than 5 calendar days, trigger incremental update
        if (today - latest_dt).days > 5:
            return None

        # Reconstruct rows in ascending chronological order
        points = []
        for r in reversed(rows):
            pt = {
                "date": r["trading_date"],
                "close": float(r["close_price"]),
                "adjustedClose": float(r["adjusted_close"]),
                "volume": int(r["volume"] or 0),
                "adjustedVolume": int(r["adjusted_volume"] or r["volume"] or 0),
                "tradingValue": float(r["trading_value"] or 0.0),
                "isPartial": bool(r["is_partial"]),
            }
            if r["open_price"] is not None:
                pt["open"] = float(r["open_price"])
            if r["high_price"] is not None:
                pt["high"] = float(r["high_price"])
            if r["low_price"] is not None:
                pt["low"] = float(r["low_price"])
            points.append(pt)

        return {
            "success": True,
            "statusCode": 200,
            "data": {
                "range": range_str,
                "from": points[0]["date"],
                "to": points[-1]["date"],
                "isPartial": points[-1]["isPartial"],
                "points": points,
            },
            "meta": {
                "source": ["local_sqlite_quant_db"],
                "as_of": points[-1]["date"],
                "unit": "VND",
                "classification": "CACHED_LOCAL",
                "formula_version": "vnsc-adjusted-close-v1",
                "served_from_local_db": True,
            }
        }
    finally:
        conn.close()


def get_cached_multi_equity_dataset(
    symbols: list[str],
    range_str: str = "1y",
    use_adjusted: bool = True,
) -> dict[str, Any] | None:
    """
    Retrieve aligned historical price, raw price, and volume DataFrames from SQLite.
    Returns None if any requested symbol lacks sufficient data.
    """
    clean_syms = [s.strip().upper() for s in symbols if s.strip()]
    if len(clean_syms) < 2:
        return None

    range_days_map = {
        "5d": 10,
        "1m": 35,
        "3m": 95,
        "6m": 190,
        "1y": 380,
        "2y": 750,
        "3y": 1120,
        "5y": 1850,
        "max": 3650,
    }
    lookback = range_days_map.get(range_str.lower(), 380)

    min_sessions_map = {
        "5d": 3,
        "1m": 15,
        "3m": 45,
        "6m": 90,
        "1y": 200,
        "2y": 400,
        "3y": 600,
        "5y": 1000,
        "max": 100,
    }
    min_required = min_sessions_map.get(range_str.lower(), 15)

    conn = get_connection()
    try:
        adj_series_list = []
        raw_series_list = []
        vol_series_list = []
        latest_raw_prices: dict[str, float] = {}

        for sym in clean_syms:
            cur = conn.execute(
                """
                SELECT trading_date, close_price, adjusted_close, volume
                FROM fact_equity_daily_prices
                WHERE symbol = ?
                ORDER BY trading_date DESC
                LIMIT ?
                """,
                (sym, lookback)
            )
            rows = cur.fetchall()
            if not rows or len(rows) < min_required:
                return None  # Insufficient rows for this symbol

            df_sym = pd.DataFrame([dict(r) for r in reversed(rows)])
            df_sym["trading_date"] = pd.to_datetime(df_sym["trading_date"])
            df_sym = df_sym.set_index("trading_date").sort_index()

            p_col = "adjusted_close" if use_adjusted else "close_price"
            df_sym[p_col] = pd.to_numeric(df_sym[p_col], errors="coerce")
            df_sym["close_price"] = pd.to_numeric(df_sym["close_price"], errors="coerce")
            df_sym["volume"] = pd.to_numeric(df_sym["volume"], errors="coerce").fillna(0.0)

            latest_raw_prices[sym] = float(df_sym["close_price"].iloc[-1])
            adj_series_list.append(df_sym[p_col].rename(sym))
            raw_series_list.append(df_sym["close_price"].rename(sym))
            vol_series_list.append(df_sym["volume"].rename(sym))

        # Aligned inner join on trading dates
        df_aligned = pd.concat(adj_series_list, axis=1, join="inner").dropna(how="any").sort_index()
        if len(df_aligned) < min_required:
            return None

        df_raw_aligned = pd.concat(raw_series_list, axis=1, join="inner").reindex(df_aligned.index)
        df_vol_aligned = pd.concat(vol_series_list, axis=1, join="inner").reindex(df_aligned.index).fillna(0.0)

        df_aligned.index.name = "Date"
        df_raw_aligned.index.name = "Date"
        df_vol_aligned.index.name = "Date"

        return {
            "symbols": clean_syms,
            "df_prices": df_aligned,
            "df_raw_prices": df_raw_aligned,
            "df_volumes": df_vol_aligned,
            "latest_raw_prices": latest_raw_prices,
            "from_date": str(df_aligned.index[0].date()),
            "to_date": str(df_aligned.index[-1].date()),
            "sessions_count": len(df_aligned) - 1,
            "range": range_str,
            "use_adjusted": use_adjusted,
            "formula_version": "vnsc-adjusted-close-v1" if use_adjusted else "raw-close",
            "source": "Local SQLite Quant DB (Zero Quota Consumed)",
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Market Indices & Upload Ingestion
# ---------------------------------------------------------------------------

def upsert_market_index_daily(index_code: str, payload: dict[str, Any]) -> int:
    """Persist VNDirect DChart API index response into fact_market_indices_daily."""
    sym = (index_code or "VNINDEX").strip().upper()
    timestamps = payload.get("t", [])
    closes = payload.get("c", [])
    opens = payload.get("o", [])
    highs = payload.get("h", [])
    lows = payload.get("l", [])
    volumes = payload.get("v", [])

    if not timestamps or not closes:
        return 0

    conn = get_connection()
    count = 0
    try:
        rows = []
        for i in range(len(timestamps)):
            ts = timestamps[i]
            d_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            c_val = float(closes[i]) if i < len(closes) else 0.0
            o_val = float(opens[i]) if i < len(opens) else c_val
            h_val = float(highs[i]) if i < len(highs) else c_val
            l_val = float(lows[i]) if i < len(lows) else c_val
            v_val = int(volumes[i]) if i < len(volumes) else 0
            rows.append((sym, d_str, o_val, h_val, l_val, c_val, v_val))

        conn.executemany(
            """
            INSERT INTO fact_market_indices_daily (index_code, trading_date, open_point, high_point, low_point, close_point, total_volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_code, trading_date) DO UPDATE SET
                open_point = excluded.open_point,
                high_point = excluded.high_point,
                low_point = excluded.low_point,
                close_point = excluded.close_point,
                total_volume = excluded.total_volume;
            """,
            rows
        )
        conn.commit()
        count = len(rows)
    finally:
        conn.close()
    return count


def get_benchmark_series_from_db(index_code: str = "VNINDEX", lookback_days: int = 380) -> pd.Series | None:
    """Retrieve benchmark closing point series from fact_market_indices_daily."""
    sym = (index_code or "VNINDEX").strip().upper()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT trading_date, close_point
            FROM fact_market_indices_daily
            WHERE index_code = ?
            ORDER BY trading_date DESC
            LIMIT ?
            """,
            (sym, lookback_days)
        )
        rows = cur.fetchall()
        if not rows or len(rows) < 10:
            return None

        dates = [datetime.strptime(r["trading_date"], "%Y-%m-%d") for r in reversed(rows)]
        closes = [float(r["close_point"]) for r in reversed(rows)]
        s = pd.Series(closes, index=pd.DatetimeIndex(dates).normalize(), name=sym, dtype=float)
        return s[~s.index.duplicated(keep="last")].sort_index()
    finally:
        conn.close()


def upsert_macro_time_series(indicator_code: str, points: list[dict[str, Any]]) -> int:
    """
    Insert or update macroeconomic time series points into fact_macro_time_series.
    Ensures indicator_code exists in dim_macro_indicators to preserve FK referential integrity.
    """
    code = (indicator_code or "").strip().upper()
    if not code or not points:
        return 0

    conn = get_connection()
    count = 0
    try:
        # Check FK existence in dim_macro_indicators
        cur = conn.execute("SELECT 1 FROM dim_macro_indicators WHERE indicator_code = ?", (code,))
        if not cur.fetchone():
            raise ValueError(f"Chỉ báo vĩ mô '{code}' chưa được định nghĩa trong dim_macro_indicators.")

        rows = []
        for p in points:
            d_str = str(p.get("date") or p.get("record_date") or "").strip()[:10]
            if not d_str:
                continue
            val = float(p.get("value", p.get("rate", 0.0)))
            bid = float(p["bid"]) if ("bid" in p and p["bid"] is not None) else None
            ask = float(p["ask"]) if ("ask" in p and p["ask"] is not None) else None
            prev = float(p["previous"]) if ("previous" in p and p["previous"] is not None) else None
            forecast = float(p["forecast"]) if ("forecast" in p and p["forecast"] is not None) else None
            chg = float(p["change"]) if ("change" in p and p["change"] is not None) else None
            chg_pct = float(p["changePercent"] or p.get("change_pct", 0.0)) if ("changePercent" in p or "change_pct" in p) else None
            lbl = str(p.get("period") or p.get("period_label") or "")

            rows.append((code, d_str, d_str, lbl, val, bid, ask, prev, forecast, chg, chg_pct))

        conn.executemany(
            """
            INSERT INTO fact_macro_time_series
            (indicator_code, record_date, published_date, period_label, value, bid_value, ask_value, previous_value, forecast_value, change_value, change_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(indicator_code, record_date) DO UPDATE SET
                value = excluded.value,
                bid_value = COALESCE(excluded.bid_value, fact_macro_time_series.bid_value),
                ask_value = COALESCE(excluded.ask_value, fact_macro_time_series.ask_value),
                previous_value = COALESCE(excluded.previous_value, fact_macro_time_series.previous_value),
                forecast_value = COALESCE(excluded.forecast_value, fact_macro_time_series.forecast_value),
                change_value = COALESCE(excluded.change_value, fact_macro_time_series.change_value),
                change_pct = COALESCE(excluded.change_pct, fact_macro_time_series.change_pct);
            """,
            rows
        )
        conn.commit()
        count = len(rows)
    finally:
        conn.close()
    return count


def get_macro_series_from_db(indicator_code: str, lookback_days: int = 380) -> list[dict[str, Any]] | None:
    """Retrieve historical macroeconomic time series from fact_macro_time_series."""
    code = (indicator_code or "").strip().upper()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT indicator_code, record_date, period_label, value, bid_value, ask_value, previous_value, forecast_value, change_value, change_pct
            FROM fact_macro_time_series
            WHERE indicator_code = ?
            ORDER BY record_date DESC
            LIMIT ?
            """,
            (code, lookback_days)
        )
        rows = cur.fetchall()
        if not rows:
            return None
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def ingest_uploaded_prices_df(df_prices: pd.DataFrame, df_volumes: pd.DataFrame | None = None) -> int:
    """
    Ingest user-uploaded clean price and volume DataFrames into fact_equity_daily_prices,
    enriching the local database without consuming API quota.
    """
    if df_prices is None or df_prices.empty:
        return 0

    conn = get_connection()
    rows = []
    try:
        syms = [str(c).strip().upper() for c in df_prices.columns]
        for s in syms:
            conn.execute(
                """
                INSERT INTO dim_equities (symbol, code, name_local, exchange, currency, trading_unit)
                VALUES (?, ?, ?, 'UPLOADED', 'VND', 100)
                ON CONFLICT(symbol) DO NOTHING;
                """,
                (s, s, f"Cổ phiếu {s}")
            )

        for d_idx, row in df_prices.iterrows():
            d_str = str(d_idx.date()) if hasattr(d_idx, "date") else str(d_idx)[:10]
            for s in syms:
                val = row[s]
                if pd.notna(val) and float(val) > 0:
                    raw_p = float(val)
                    vol = 0
                    if df_volumes is not None and s in df_volumes.columns:
                        try:
                            v_val = df_volumes.loc[d_idx, s]
                            if pd.notna(v_val):
                                vol = int(v_val)
                        except Exception:
                            vol = 0
                    rows.append((s, d_str, raw_p, raw_p, vol, vol, raw_p * vol, 0))

        conn.executemany(
            """
            INSERT INTO fact_equity_daily_prices
            (symbol, trading_date, close_price, adjusted_close, volume, adjusted_volume, trading_value, is_partial)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trading_date) DO UPDATE SET
                close_price = excluded.close_price,
                adjusted_close = excluded.adjusted_close,
                volume = excluded.volume,
                trading_value = excluded.trading_value;
            """,
            rows
        )
        conn.commit()
    finally:
        conn.close()

    return len(rows)


# ---------------------------------------------------------------------------
# Database Inspection & Analytics Summary
# ---------------------------------------------------------------------------

def get_database_summary() -> dict[str, Any]:
    """Retrieve full health, table counts, file size, and rate limit status."""
    init_db()
    conn = get_connection()
    summary: dict[str, Any] = {
        "db_file": str(DB_PATH),
        "db_size_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 3) if DB_PATH.exists() else 0.0,
        "tables": {},
        "latest_sync_logs": [],
        "sample_dashboard": [],
    }

    tables = [
        "dim_equities",
        "dim_market_indices",
        "dim_macro_indicators",
        "fact_equity_daily_prices",
        "fact_market_indices_daily",
        "fact_macro_time_series",
        "fact_equity_financial_ratios",
        "sys_sync_logs",
    ]

    try:
        for t in tables:
            cur = conn.execute(f"SELECT COUNT(*) AS cnt FROM {t}")
            summary["tables"][t] = cur.fetchone()["cnt"]

        # Latest sync logs
        cur = conn.execute(
            "SELECT resource_id, sync_scope, last_synced_date, records_upserted, rate_limit_remaining, last_sync_at FROM sys_sync_logs ORDER BY last_sync_at DESC LIMIT 10"
        )
        summary["latest_sync_logs"] = [dict(r) for r in cur.fetchall()]

        # Sample from vw_equity_master_dashboard
        cur = conn.execute(
            "SELECT symbol, name_local, exchange, sector_name, latest_date, close_price, pe_ratio, roe FROM vw_equity_master_dashboard LIMIT 5"
        )
        summary["sample_dashboard"] = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    return summary
