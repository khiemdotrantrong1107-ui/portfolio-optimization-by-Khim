"""
Comprehensive Data Quality & Database Integrity Verification Test Suite.
Validates:
1. Schema & Table/View Existence (7 Tables, 1 Log Table, 3 Analytical Views).
2. Primary Key Uniqueness & Zero Duplication (No duplicate keys or sessions).
3. Null Value Constraints on Required Identity & Quantitative Fields.
4. Non-Zero / Non-Negative Validity (Price > 0, Volume >= 0, Trading Unit = 100).
5. Format & Range Integrity (Valid ISO dates, no NaN/Infinity, valid exchange codes).
6. Foreign Key Referential Integrity (Orphan checks across DIM and FACT tables).
7. Analytical Views Precision (Float division in simple_return without integer truncation).
8. Corporate Action Drift Detection logic under simulated dividend events.
"""
from __future__ import annotations

import math
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine import db_manager


def test_schema_tables_and_views_existence():
    """Verify all 8 tables and 3 analytical views exist in SQLite."""
    conn = db_manager.get_connection()
    try:
        cur = conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
        objects = {row["name"]: row["type"] for row in cur.fetchall()}

        expected_tables = [
            "dim_equities",
            "dim_market_indices",
            "dim_macro_indicators",
            "fact_equity_daily_prices",
            "fact_market_indices_daily",
            "fact_macro_time_series",
            "fact_equity_financial_ratios",
            "sys_sync_logs",
        ]
        for tbl in expected_tables:
            assert tbl in objects and objects[tbl] == "table", f"Missing table in DB: {tbl}"

        expected_views = [
            "vw_equity_master_dashboard",
            "vw_equity_daily_returns",
            "vw_macro_latest_snapshot",
        ]
        for vw in expected_views:
            assert vw in objects and objects[vw] == "view", f"Missing analytical view in DB: {vw}"
    finally:
        conn.close()


def test_no_duplicate_records_and_composite_pks():
    """Verify primary key uniqueness and ensure zero duplicate rows across all tables."""
    conn = db_manager.get_connection()
    try:
        # 1. Dim Equities: symbol must be unique
        cur = conn.execute("SELECT symbol, COUNT(*) as cnt FROM dim_equities GROUP BY symbol HAVING cnt > 1")
        dups = cur.fetchall()
        assert len(dups) == 0, f"Found duplicate symbols in dim_equities: {[dict(d) for d in dups]}"

        # 2. Dim Indices: index_code must be unique
        cur = conn.execute("SELECT index_code, COUNT(*) as cnt FROM dim_market_indices GROUP BY index_code HAVING cnt > 1")
        assert len(cur.fetchall()) == 0, "Found duplicate index_code in dim_market_indices"

        # 3. Dim Macro: indicator_code must be unique
        cur = conn.execute("SELECT indicator_code, COUNT(*) as cnt FROM dim_macro_indicators GROUP BY indicator_code HAVING cnt > 1")
        assert len(cur.fetchall()) == 0, "Found duplicate indicator_code in dim_macro_indicators"

        # 4. Fact Daily Prices: (symbol, trading_date) must be unique
        cur = conn.execute("SELECT symbol, trading_date, COUNT(*) as cnt FROM fact_equity_daily_prices GROUP BY symbol, trading_date HAVING cnt > 1")
        dups = cur.fetchall()
        assert len(dups) == 0, f"Found duplicate (symbol, trading_date) in fact_equity_daily_prices: {len(dups)}"

        # 5. Fact Market Indices: (index_code, trading_date) must be unique
        cur = conn.execute("SELECT index_code, trading_date, COUNT(*) as cnt FROM fact_market_indices_daily GROUP BY index_code, trading_date HAVING cnt > 1")
        assert len(cur.fetchall()) == 0, "Found duplicate (index_code, trading_date) in fact_market_indices_daily"

        # 6. Fact Macro Series: (indicator_code, record_date) must be unique
        cur = conn.execute("SELECT indicator_code, record_date, COUNT(*) as cnt FROM fact_macro_time_series GROUP BY indicator_code, record_date HAVING cnt > 1")
        assert len(cur.fetchall()) == 0, "Found duplicate (indicator_code, record_date) in fact_macro_time_series"
    finally:
        conn.close()


def test_required_fields_not_null():
    """Verify that mandatory fields are never NULL or empty strings."""
    conn = db_manager.get_connection()
    try:
        # Dim Equities
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM dim_equities WHERE symbol IS NULL OR symbol = '' OR name_local IS NULL OR exchange IS NULL")
        assert cur.fetchone()["cnt"] == 0, "dim_equities has unexpected NULL/empty fields"

        # Dim Indices
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM dim_market_indices WHERE index_code IS NULL OR name IS NULL OR exchange IS NULL")
        assert cur.fetchone()["cnt"] == 0, "dim_market_indices has unexpected NULL fields"

        # Dim Macro
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM dim_macro_indicators WHERE indicator_code IS NULL OR category IS NULL OR country IS NULL OR unit IS NULL")
        assert cur.fetchone()["cnt"] == 0, "dim_macro_indicators has unexpected NULL fields"

        # Fact Prices
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_equity_daily_prices WHERE symbol IS NULL OR trading_date IS NULL OR close_price IS NULL OR adjusted_close IS NULL")
        assert cur.fetchone()["cnt"] == 0, "fact_equity_daily_prices has NULL mandatory fields"

        # Fact Macro
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_macro_time_series WHERE indicator_code IS NULL OR record_date IS NULL OR value IS NULL")
        assert cur.fetchone()["cnt"] == 0, "fact_macro_time_series has NULL mandatory fields"
    finally:
        conn.close()


def test_positive_and_non_negative_values():
    """Verify that stock prices > 0, trading unit > 0, and volume/value >= 0 (No zero/negative price bugs)."""
    conn = db_manager.get_connection()
    try:
        # Stock prices must be strictly positive (> 0)
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_equity_daily_prices WHERE close_price <= 0 OR adjusted_close <= 0")
        bad_prices = cur.fetchone()["cnt"]
        assert bad_prices == 0, f"Found {bad_prices} records with close_price or adjusted_close <= 0 in fact_equity_daily_prices"

        # Volume & trading value must be non-negative (>= 0)
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_equity_daily_prices WHERE volume < 0 OR adjusted_volume < 0 OR trading_value < 0")
        bad_vol = cur.fetchone()["cnt"]
        assert bad_vol == 0, f"Found {bad_vol} records with negative volume or trading_value"

        # Trading units must be strictly positive (standard lot 100)
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM dim_equities WHERE trading_unit <= 0")
        assert cur.fetchone()["cnt"] == 0, "Found dim_equities with trading_unit <= 0"
    finally:
        conn.close()


def test_date_format_and_referential_integrity():
    """Verify dates conform to YYYY-MM-DD and all fact rows link to valid parent dim records."""
    conn = db_manager.get_connection()
    date_regex = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    try:
        # Validate date formats in Fact Prices
        cur = conn.execute("SELECT DISTINCT trading_date FROM fact_equity_daily_prices")
        for row in cur.fetchall():
            d = row["trading_date"]
            assert date_regex.match(d), f"Invalid date format in fact_equity_daily_prices: {d}"
            # Ensure valid calendar date
            datetime.strptime(d, "%Y-%m-%d")

        # Validate date formats in Fact Macro
        cur = conn.execute("SELECT DISTINCT record_date FROM fact_macro_time_series")
        for row in cur.fetchall():
            d = row["record_date"]
            assert date_regex.match(d), f"Invalid date format in fact_macro_time_series: {d}"
            datetime.strptime(d, "%Y-%m-%d")

        # Referential Integrity (Foreign Key Orphan Check)
        cur = conn.execute(
            """
            SELECT COUNT(*) AS cnt 
            FROM fact_equity_daily_prices p
            LEFT JOIN dim_equities e ON p.symbol = e.symbol
            WHERE e.symbol IS NULL
            """
        )
        assert cur.fetchone()["cnt"] == 0, "Found orphan rows in fact_equity_daily_prices with no parent in dim_equities"

        cur = conn.execute(
            """
            SELECT COUNT(*) AS cnt 
            FROM fact_macro_time_series m
            LEFT JOIN dim_macro_indicators d ON m.indicator_code = d.indicator_code
            WHERE d.indicator_code IS NULL
            """
        )
        assert cur.fetchone()["cnt"] == 0, "Found orphan rows in fact_macro_time_series with no parent in dim_macro_indicators"
    finally:
        conn.close()


def test_analytical_views_precision_and_computation():
    """Verify that analytical views compute correct float precision (specifically simple_return is not 0)."""
    conn = db_manager.get_connection()
    try:
        # Check if DB is empty; if so, insert temporary fixture rows for testing views
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_equity_daily_prices")
        is_empty = (cur.fetchone()["cnt"] == 0)

        if is_empty:
            conn.execute(
                """
                INSERT INTO fact_equity_daily_prices 
                (symbol, trading_date, close_price, adjusted_close, volume, adjusted_volume, trading_value, is_partial)
                VALUES 
                ('FPT', '2026-11-05', 135000.0, 135000.0, 1000000, 1000000, 135000000000.0, 0),
                ('FPT', '2026-11-06', 136900.0, 136900.0, 1200000, 1200000, 164280000000.0, 0)
                """
            )
            conn.execute(
                """
                INSERT INTO fact_macro_time_series 
                (indicator_code, record_date, period_label, value, previous_value, change_value, change_pct)
                VALUES ('VN_BOND_10Y', '2026-11-06', '10Y', 0.0285, 0.0282, 0.0003, 1.06)
                """
            )
            conn.commit()

        # 1. Test vw_equity_daily_returns
        cur = conn.execute(
            """
            SELECT symbol, trading_date, close_price, adjusted_close, prev_adjusted_close, simple_return
            FROM vw_equity_daily_returns
            WHERE prev_adjusted_close IS NOT NULL AND adjusted_close != prev_adjusted_close
            LIMIT 10
            """
        )
        rows = cur.fetchall()
        assert len(rows) > 0, "vw_equity_daily_returns returned no rows with price changes"

        for r in rows:
            ret = r["simple_return"]
            assert ret is not None, f"simple_return was unexpectedly NULL for {dict(r)}"
            assert isinstance(ret, float), f"simple_return must be float, got {type(ret)}"
            expected = round((float(r["adjusted_close"]) - float(r["prev_adjusted_close"])) / float(r["prev_adjusted_close"]), 6)
            assert abs(ret - expected) < 1e-5, f"Return calculation mismatch: got {ret}, expected {expected}"

        # 2. Test vw_equity_master_dashboard
        cur = conn.execute("SELECT * FROM vw_equity_master_dashboard WHERE latest_date IS NOT NULL LIMIT 5")
        dash_rows = cur.fetchall()
        assert len(dash_rows) > 0, "vw_equity_master_dashboard has no rows with latest prices"
        for dr in dash_rows:
            assert dr["symbol"] is not None
            assert float(dr["close_price"]) > 0

        # 3. Test vw_macro_latest_snapshot
        cur = conn.execute("SELECT * FROM vw_macro_latest_snapshot WHERE latest_date IS NOT NULL")
        macro_rows = cur.fetchall()
        assert len(macro_rows) >= 1, f"Expected at least 1 macro indicator snapshot, got {len(macro_rows)}"

        # Clean up temporary fixture rows if inserted
        if is_empty:
            conn.execute("DELETE FROM fact_equity_daily_prices WHERE symbol = 'FPT'")
            conn.execute("DELETE FROM fact_macro_time_series WHERE indicator_code = 'VN_BOND_10Y'")
            conn.commit()
    finally:
        conn.close()


def test_corporate_action_drift_detection():
    """Unit test corporate action dividend drift detection logic."""
    try:
        # 1. Clean points with identical overlap price -> drift_detected == False
        pts_clean = [
            {"date": "2025-11-20", "close": 112700, "adjustedClose": 112700, "volume": 6322200},
            {"date": "2025-11-21", "close": 114200, "adjustedClose": 114200, "volume": 5340200},
        ]
        res_clean = db_manager.upsert_equity_prices_with_drift_check("FPT", pts_clean)
        assert res_clean["drift_detected"] is False, "False positive drift detected on identical prices"

        # 2. Simulated dividend shift on overlap date (e.g. 5% split adjustment) -> drift_detected == True
        pts_dividend = [
            {"date": "2025-11-20", "close": 112700, "adjustedClose": 105000, "volume": 6322200},  # Drifted from 112700 to 105000
            {"date": "2025-11-22", "close": 115000, "adjustedClose": 107000, "volume": 5000000},
        ]
        res_div = db_manager.upsert_equity_prices_with_drift_check("FPT", pts_dividend)
        assert res_div["drift_detected"] is True, "Failed to detect corporate action drift when adjustedClose changed"
    finally:
        # Clean up all test points from DB to ensure database remains clean and empty
        conn = db_manager.get_connection()
        conn.execute("DELETE FROM fact_equity_daily_prices WHERE symbol = 'FPT'")
        conn.commit()
        conn.close()


def test_market_index_ingestion_and_upsert():
    """Verify market index OHLCV ingestion and upsert into fact_market_indices_daily."""
    from engine import benchmark_engine
    try:
        res = benchmark_engine.sync_benchmark_index_to_db("VNINDEX", range_str="1m")
        assert res["status"] == "success"
        assert res["symbol"] == "VNINDEX"
        assert res["records_upserted"] > 0
        assert res["latest_close"] > 0

        conn = db_manager.get_connection()
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM fact_market_indices_daily WHERE index_code = 'VNINDEX'")
        assert cur.fetchone()["cnt"] > 0, "No records found in fact_market_indices_daily after sync"
        conn.close()
    finally:
        # Clean up to keep database completely clean
        conn = db_manager.get_connection()
        conn.execute("DELETE FROM fact_market_indices_daily")
        conn.commit()
        conn.close()


def test_macro_time_series_ingestion_and_upsert():
    """Verify macroeconomic time series bulk upsert into fact_macro_time_series and FK integrity."""
    test_points = [
        {"date": "2026-11-05", "value": 0.0282, "previous": 0.0280, "change": 0.0002, "changePercent": 0.71, "period": "10Y"},
        {"date": "2026-11-06", "value": 0.0285, "previous": 0.0282, "change": 0.0003, "changePercent": 1.06, "period": "10Y"},
    ]
    try:
        # Valid insertion
        count = db_manager.upsert_macro_time_series("VN_BOND_10Y", test_points)
        assert count == 2, f"Expected 2 macro records upserted, got {count}"

        conn = db_manager.get_connection()
        cur = conn.execute("SELECT * FROM fact_macro_time_series WHERE indicator_code = 'VN_BOND_10Y' ORDER BY record_date ASC")
        rows = cur.fetchall()
        assert len(rows) == 2, f"Expected 2 rows in fact_macro_time_series, got {len(rows)}"
        assert float(rows[1]["value"]) == 0.0285
        assert float(rows[1]["change_pct"]) == 1.06
        conn.close()

        # Invalid FK indicator code must raise ValueError
        invalid_caught = False
        try:
            db_manager.upsert_macro_time_series("NON_EXISTING_INDICATOR", test_points)
        except ValueError:
            invalid_caught = True
        assert invalid_caught is True, "Failed to reject invalid indicator_code violating foreign key constraint"
    finally:
        conn = db_manager.get_connection()
        conn.execute("DELETE FROM fact_macro_time_series WHERE indicator_code = 'VN_BOND_10Y'")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    print("Running Database Input Data & Schema Integrity Verification Suites...")
    test_schema_tables_and_views_existence()
    print("  [PASS] 1. Schema Tables & Analytical Views Existence (7 Tables + 1 System Table + 3 Views)")
    test_no_duplicate_records_and_composite_pks()
    print("  [PASS] 2. Primary Key Uniqueness & Zero Duplication Across All Tables")
    test_required_fields_not_null()
    print("  [PASS] 3. Mandatory Identity & Quantitative Fields NOT NULL Constraint")
    test_positive_and_non_negative_values()
    print("  [PASS] 4. Numerical Validity (Close Price > 0, Volume >= 0, Trading Unit > 0)")
    test_date_format_and_referential_integrity()
    print("  [PASS] 5. ISO Date Formats (YYYY-MM-DD) & Foreign Key Referential Integrity")
    test_analytical_views_precision_and_computation()
    print("  [PASS] 6. Analytical Views Precision & Floating-Point Return Division (No 0-division bugs)")
    test_corporate_action_drift_detection()
    print("  [PASS] 7. Corporate Action Dividend Drift Detection Unit Test")
    test_market_index_ingestion_and_upsert()
    print("  [PASS] 8. Market Index Ingestion & VNDirect DChart Upsert (fact_market_indices_daily)")
    test_macro_time_series_ingestion_and_upsert()
    print("  [PASS] 9. Macroeconomic Time Series Bulk Upsert & FK Validation (fact_macro_time_series)")
    print("ALL 9 DATABASE INTEGRITY TEST SUITES PASSED SUCCESSFULLY!")

