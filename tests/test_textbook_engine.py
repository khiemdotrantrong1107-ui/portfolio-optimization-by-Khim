"""
Comprehensive Verification Test Suite for Markowitz Portfolio Optimization (v2.5.0).
Covers original regression suites plus independent mathematical tests and the 10
end-to-end integration consistency, constraint, provenance, snapshot, and UI/i18n suites.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app import (
    BenchmarkAttributionRequest,
    OptimizeRequest,
    api_benchmark_attribution,
    api_export_excel,
    api_export_matrix,
    api_export_prices,
    api_get_presets,
    api_optimize,
    api_quote_ticker,
    api_search_tickers,
    app,
)
from engine import (
    benchmark_engine,
    data_loader,
    execution_engine,
    hayinsights_client,
    risk_profiler,
    template_generator,
    textbook_math,
)


def test_merton_closed_form_identities():
    """Verify exact textbook identities: sigma^2_gmv = 1/C and E(R_gmv) = A/C."""
    symbols = ["A1", "A2", "A3"]
    er = [0.20, 0.14, 0.10]
    std = [0.25, 0.18, 0.12]
    corr = [
        [1.0, 0.3, 0.1],
        [0.3, 1.0, 0.2],
        [0.1, 0.2, 1.0],
    ]
    moments = textbook_math.build_moments_from_manual(symbols, er, std, corr)
    sol = textbook_math.solve_merton_closed_form(moments["mu"], moments["cov"], rf=0.04)

    sc = sol["merton_scalars"]
    assert sc["C"] > 0
    assert sc["D"] > 0
    assert abs(np.sum(sol["w_gmv"]) - 1.0) < 1e-7
    assert abs(np.sum(sol["w_tangency"]) - 1.0) < 1e-7
    assert abs(sol["gmv_stats"]["expected_return"] - (sc["A"] / sc["C"])) < 1e-7
    assert abs(sol["gmv_stats"]["variance"] - (1.0 / sc["C"])) < 1e-7


def test_long_only_qp_constraints():
    """Verify that Long-Only QP strictly satisfies w_i >= 0 and sum(w_i) = 1 on real market data."""
    live = hayinsights_client.fetch_multi_equity_dataset(["FPT", "MWG", "VCB", "HPG"], range_str="1y")
    moments = textbook_math.compute_moments_from_prices(live["df_prices"], trading_days=252)
    sol = textbook_math.solve_long_only_qp(moments["mu"], moments["cov"], rf=0.045, allow_short=False)

    assert abs(np.sum(sol["w_gmv"]) - 1.0) < 1e-6
    assert np.all(sol["w_gmv"] >= -1e-6)
    assert abs(np.sum(sol["w_tangency"]) - 1.0) < 1e-6
    assert np.all(sol["w_tangency"] >= -1e-6)
    assert sol["tangency_stats"]["sharpe_ratio"] >= sol["gmv_stats"]["sharpe_ratio"] - 1e-5


def test_risk_profiler_quiz():
    """Verify 4-question quiz scoring, strict validation, and mapping to gamma."""
    conservative = risk_profiler.evaluate_risk_profile([1, 1, 1, 1])
    assert conservative["total_score"] == 4
    assert conservative["risk_aversion_gamma"] == 8.0
    assert conservative["risk_aversion_A"] == 8.0

    aggressive = risk_profiler.evaluate_risk_profile([4, 4, 4, 4])
    assert aggressive["total_score"] == 16
    assert aggressive["risk_aversion_gamma"] == 1.2

    try:
        risk_profiler.evaluate_risk_profile([2, 3, 2])
        raise AssertionError("Should reject <4 quiz answers")
    except ValueError:
        pass


def test_template_and_upload_roundtrip():
    """Verify generating input Excel templates (parameters & prices) and parsing them back."""
    xlsx_bytes = template_generator.generate_input_template_xlsx(mode="parameters")
    parsed = data_loader.parse_uploaded_file(xlsx_bytes, "template.xlsx")
    assert len(parsed["symbols"]) >= 3
    assert len(parsed["mu"]) == len(parsed["symbols"])

    prices_bytes = template_generator.generate_input_template_xlsx(mode="prices")
    parsed_p = data_loader.parse_uploaded_file(prices_bytes, "prices.xlsx")
    assert len(parsed_p["symbols"]) >= 3
    assert parsed_p["source_type"] == "uploaded_prices"
    assert parsed_p["dataset_id"]


def test_institutional_excel_export_8_sheets():
    """Verify 8-sheet Excel workbook exports cleanly with live SUM formulas & Stress/Benchmark tabs."""
    req = OptimizeRequest(
        input_mode="live_market",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM"],
        rf=0.045,
        risk_aversion_A=3.0,
        allow_short=True,
        benchmark_symbol="VNINDEX",
        benchmark_range="1y",
        nav_vnd=1_000_000_000.0,
        lang="en",
    )
    opt_res = api_optimize(req)
    assert opt_res["status"] == "success"
    assert 2 <= len(opt_res["frontier"]) <= 50

    res = api_export_excel(req)
    assert res.status_code == 200
    wb = load_workbook(io.BytesIO(res.body), data_only=False)
    expected_sheets = [
        "01_Executive_Summary",
        "02_Asset_Statistics",
        "03_Covariance_Correlation",
        "04_Matrix_Calculations",
        "05_Efficient_Frontier_Data",
        "06_Execution_Order_Sheet",
        "07_Benchmark_Scorecard",
        "08_Stress_Testing_VaR",
    ]
    assert wb.sheetnames == expected_sheets
    ws1 = wb["01_Executive_Summary"]
    assert str(ws1["D26"].value).startswith("=SUM(")
    ws7 = wb["07_Benchmark_Scorecard"]
    assert "BENCHMARK SCORECARD" in str(ws7["A1"].value)
    ws8 = wb["08_Stress_Testing_VaR"]
    assert "STRESS TESTING" in str(ws8["A1"].value)
    assert "Value at Risk (VaR 95%)" in str(ws8["A7"].value)


def test_hayinsights_live_api_integration():
    """Verify live HayInsights API fetch for non-preset tickers, autocomplete search, and MVO solve."""
    presets = api_get_presets()
    assert presets["hayinsights_configured"] is True
    assert len(presets["ticker_directory"]) >= 120

    res_vc = api_search_tickers(q="VC")
    vc_syms = [r["symbol"] for r in res_vc["results"]]
    assert "VCB" in vc_syms and "VCI" in vc_syms and "VCG" in vc_syms

    quote_dgc = api_quote_ticker("DGC")
    assert quote_dgc["valid"] is True
    assert quote_dgc["latest_price"] > 0

    req = OptimizeRequest(
        input_mode="live_market",
        symbols=["DGC", "ACB", "PVS", "BSR", "KDH", "VCI"],
        hayinsights_range="1y",
        use_adjusted_close=True,
        rf=0.045,
        risk_aversion_A=3.0,
        allow_short=False,
        nav_vnd=1_000_000_000.0,
    )
    opt_res = api_optimize(req)
    assert opt_res["status"] == "success"
    assert opt_res["symbols"] == ["DGC", "ACB", "PVS", "BSR", "KDH", "VCI"]
    assert opt_res["sessions_count"] >= 200
    assert abs(sum(opt_res["tangency"]["weights"]) - 1.0) < 1e-6


def test_bounded_qp_and_fixed_cash_no_auto_relax():
    """Verify bounded QP stays within equity bounds and fixed cash holds without auto-relaxation."""
    req_bounded = OptimizeRequest(
        input_mode="live_market",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM", "SSI"],
        w_min=0.05,
        w_max=0.20,
        cash_mode="fixed_cash",
        mandated_cash_pct=0.15,
        nav_vnd=2_000_000_000.0,
    )
    res = api_optimize(req_bounded)
    w_tan = res["tangency"]["weights"]
    w_gmv = res["gmv"]["weights"]
    assert abs(sum(w_tan) - 1.0) < 1e-5
    assert abs(sum(w_gmv) - 1.0) < 1e-5
    for w in w_tan:
        assert 0.05 - 1e-4 <= w <= 0.20 + 1e-4
    for w in w_gmv:
        assert 0.05 - 1e-4 <= w <= 0.20 + 1e-4

    # Monte Carlo must strictly sit within bounded GMV/Frontier/Tangency feasible region
    mc_pts = res["monte_carlo"]
    assert len(mc_pts) >= 100
    gmv_vol_pct = res["gmv"]["volatility"] * 100.0
    tan_sr = res["tangency"]["sharpe_ratio"]
    max_fr_ret_pct = max(p["return"] for p in res["frontier"]) * 100.0
    for pt in mc_pts:
        assert pt["volatility"] >= gmv_vol_pct - 0.02, f"MC point {pt} left of bounded GMV ({gmv_vol_pct}%)"
        assert pt["sharpe"] <= tan_sr + 0.015, f"MC point {pt} exceeded bounded Tangency SR ({tan_sr})"
        assert pt["return"] <= max_fr_ret_pct + 0.02, f"MC point {pt} exceeded bounded max return ({max_fr_ret_pct}%)"

    comp = res["complete_portfolio"]
    assert abs(comp["w_rf_weight"] - 0.15) < 1e-6
    assert abs(comp["y_star_risky_weight"] - 0.85) < 1e-6
    assert abs(sum(comp["asset_weights"]) - 0.85) < 1e-5


def test_benchmark_and_stress_testing_engine():
    """Verify Benchmark Attribution Base=100 alignment and dual-basis VaR/ES calculation."""
    req = OptimizeRequest(
        input_mode="live_market",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM"],
        benchmark_symbol="VN30",
        benchmark_range="1y",
        cash_mode="fixed_cash",
        mandated_cash_pct=0.10,
        nav_vnd=1_000_000_000.0,
    )
    res = api_optimize(req)
    bm = res["benchmark_comparison"]
    assert bm["status"] == "available"
    assert bm["benchmark_symbol"] == "VN30"
    assert bm["benchmark_range"] == "1Y"
    assert abs(bm["cumulative_series"]["portfolio_base100"][0] - 100.0) < 1e-6
    assert abs(bm["cumulative_series"]["benchmark_base100"][0] - 100.0) < 1e-6

    st = res["stress_testing"]
    assert "target_complete" in st["profiles"] and "executed_post_fee" in st["profiles"]
    vm = st["var_metrics"]
    assert vm["var_95_1d_pct"] > 0
    assert vm["var_99_1d_pct"] >= vm["var_95_1d_pct"]
    assert vm["cvar_95_1d_pct"] >= vm["var_95_1d_pct"]
    assert len(st["scenarios"]) == 4


def test_live_price_and_matrix_exports_and_benchmark_horizons():
    """Verify active Price & Matrix exports, roundtrip parsing, and benchmark horizons."""
    syms = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    req = OptimizeRequest(
        input_mode="live_market",
        symbols=syms,
        hayinsights_range="1y",
        use_adjusted_close=True,
        benchmark_symbol="VNINDEX",
        benchmark_range="6m",
    )
    opt_res = api_optimize(req)
    assert opt_res["benchmark_comparison"]["benchmark_range"] == "6M"

    res_prices = api_export_prices(req)
    assert res_prices.status_code == 200
    assert "Portfolio_Prices_5Assets_1Y_" in res_prices.headers.get("content-disposition", "")
    wb_p = load_workbook(io.BytesIO(res_prices.body), data_only=True)
    assert wb_p.sheetnames == ["Historical_Prices", "Trading_Volume", "Daily_Returns", "Universe_Summary"]

    roundtrip_p = data_loader.parse_uploaded_file(res_prices.body, "Portfolio_Prices_5Assets.xlsx")
    assert roundtrip_p["symbols"] == syms
    assert np.allclose(roundtrip_p["mu"], opt_res["mu"], atol=1e-4)

    res_mat = api_export_matrix(req)
    assert res_mat.status_code == 200
    wb_m = load_workbook(io.BytesIO(res_mat.body), data_only=True)
    assert wb_m.sheetnames == ["Parameters", "Covariance_Matrix", "Asset_Statistics"]
    roundtrip_m = data_loader.parse_uploaded_file(res_mat.body, "Portfolio_Matrix_5Assets.xlsx")
    assert roundtrip_m["symbols"] == syms
    assert np.allclose(roundtrip_m["mu"], opt_res["mu"], atol=1e-5)

    for hz in ("ytd", "3y", "max"):
        req_hz = OptimizeRequest(
            input_mode="live_market",
            symbols=["FPT", "VCB", "HPG"],
            hayinsights_range="1y",
            benchmark_symbol="VNINDEX",
            benchmark_range=hz,
        )
        res_hz = api_optimize(req_hz)
        assert res_hz["benchmark_comparison"]["benchmark_range"] == hz.upper()
        assert len(res_hz["benchmark_comparison"]["cumulative_series"]["dates"]) >= 10


def test_math_edge_cases_independent():
    """Independent mathematical tests: singular covariance, no positive excess, y clamp, quantile VaR/ES, rolling 21d."""
    # 1. Singular covariance (collinear returns)
    mu_sing = np.array([0.15, 0.15, 0.10])
    std_sing = np.array([0.20, 0.20, 0.15])
    corr_sing = np.array([
        [1.0, 1.0, 0.2],
        [1.0, 1.0, 0.2],
        [0.2, 0.2, 1.0],
    ])
    mom_sing = textbook_math.build_moments_from_manual(["S1", "S2", "S3"], mu_sing, std_sing, corr_sing)
    sol_sing = textbook_math.solve_long_only_qp(mom_sing["mu"], mom_sing["cov"], rf=0.04, allow_short=False)
    assert sol_sing["is_covariance_invertible"] is False
    assert sol_sing["merton_status"] == "singular_covariance"
    assert sol_sing["inv_cov"] is None
    assert abs(np.sum(sol_sing["w_gmv"]) - 1.0) < 1e-6

    # 2. No positive excess return (all mu <= rf) -> tangency_status & y* = 0 in utility_no_leverage
    mu_neg = np.array([0.02, 0.03, 0.01])
    cov_pos = np.diag([0.04, 0.09, 0.02])
    sol_neg = textbook_math.solve_long_only_qp(mu_neg, cov_pos, rf=0.05, allow_short=False)
    assert sol_neg["tangency_status"] == "no_positive_excess_return"
    comp_neg = textbook_math.compute_complete_portfolio(
        tangency_stats=sol_neg["tangency_stats"],
        w_tangency=sol_neg["w_tangency"],
        rf=0.05,
        risk_aversion_A=3.0,
        cash_mode="utility_no_leverage",
        tangency_status=sol_neg["tangency_status"],
    )
    assert comp_neg["y_star_risky_weight"] == 0.0
    assert comp_neg["w_rf_weight"] == 1.0

    # 3. y* > 1 clamp & zero vol edge
    comp_clamp = textbook_math.compute_complete_portfolio(
        tangency_stats={"expected_return": 0.40, "volatility": 0.15, "variance": 0.0225, "sharpe_ratio": 2.3},
        w_tangency=np.array([0.5, 0.5]),
        rf=0.04,
        risk_aversion_A=1.0,
        cash_mode="utility_no_leverage",
    )
    assert comp_clamp["y_star_unconstrained"] > 1.0
    assert comp_clamp["y_star_risky_weight"] == 1.0
    assert comp_clamp["clamp_reason"] == "clamped_to_one_no_leverage"

    # 4. Exact empirical 5th percentile & rolling 21-day compounded VaR/ES (no sqrt(21) on hist ES99!)
    rng = np.random.default_rng(7)
    daily_vals = np.linspace(-0.08, 0.06, 60) + rng.normal(0, 0.002, 60)
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    df_ret = pd.DataFrame({"A": daily_vals, "B": daily_vals * 0.5}, index=dates)
    st_res = benchmark_engine.compute_stress_testing_and_var(
        df_asset_returns=df_ret,
        w_tangency=np.array([1.0, 0.0]),
        tangency_stats={"expected_return": 0.10, "volatility": 0.20},
        complete_stats={"y_star_risky_weight": 1.0, "w_rf_weight": 0.0, "expected_return": 0.10, "volatility": 0.20},
        beta=1.0,
        nav_vnd=1_000_000_000.0,
        rf=0.04,
    )
    vm = st_res["var_metrics"]
    q5_manual = float(np.quantile(daily_vals, 0.05))
    expected_var95_1d = max(0.0, -q5_manual)
    expected_es95_1d = max(0.0, -float(np.mean(daily_vals[daily_vals <= q5_manual])))
    assert abs(vm["var_95_1d_pct"] - expected_var95_1d) < 1e-9
    assert abs(vm["cvar_95_1d_pct"] - expected_es95_1d) < 1e-9

    # Independent rolling 21d compounded verification
    rolling_21 = np.array([float(np.prod(1.0 + daily_vals[i : i + 21]) - 1.0) for i in range(60 - 20)])
    q5_21 = float(np.quantile(rolling_21, 0.05))
    assert st_res["horizon_21d_method"] == "Historical Rolling 21-Session Compounded"
    assert abs(vm["var_95_21d_pct"] - max(0.0, -q5_21)) < 1e-9

    # 5. Missing history returns None for MDD and empty scenarios
    st_mat = benchmark_engine.compute_stress_testing_and_var(
        df_asset_returns=None,
        w_tangency=np.array([0.5, 0.5]),
        tangency_stats={"expected_return": 0.15, "volatility": 0.20},
        complete_stats={"y_star_risky_weight": 0.90, "w_rf_weight": 0.10, "expected_return": 0.14, "volatility": 0.18},
        beta=None,
        nav_vnd=1_000_000_000.0,
        rf=0.04,
    )
    assert st_mat["var_metrics"]["max_drawdown_complete_pct"] is None
    assert st_mat["scenarios"] == []
    assert st_mat["stress_status"] == "unavailable_no_beta_history"


def test_ten_end_to_end_integration_suites():
    """Execute the 10 mandatory FastAPI TestClient end-to-end consistency suites."""
    client = TestClient(app)

    # Suite 1: Complete 100% Cash (y = 0 via all mu <= rf in utility_no_leverage) -> 0 shares & 0 fee
    r1 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["A1", "A2", "A3"],
        "expected_returns": [0.02, 0.03, 0.01],
        "std_devs": [0.20, 0.22, 0.18],
        "corr_matrix": [[1.0, 0.3, 0.2], [0.3, 1.0, 0.1], [0.2, 0.1, 1.0]],
        "latest_prices": {"A1": 50000, "A2": 60000, "A3": 40000},
        "rf": 0.05,
        "cash_mode": "utility_no_leverage",
        "nav_vnd": 1_000_000_000,
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["tangency_status"] == "no_positive_excess_return"
    assert d1["complete_portfolio"]["y_star_risky_weight"] == 0.0
    assert d1["execution"]["status"] == "ready"
    assert all(o["lots"] == 0 and o["shares"] == 0 for o in d1["execution"]["orders"])
    assert d1["execution"]["total_purchase_value"] == 0.0
    assert d1["execution"]["total_buy_fees"] == 0.0
    assert d1["execution"]["cash_remaining"] == 1_000_000_000.0

    # Suite 2: Fixed Cash 10% + Buy Fee 0.15% reconciliation within <= 1 VND
    r2 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["FPT", "MWG", "VCB"],
        "expected_returns": [0.22, 0.16, 0.14],
        "std_devs": [0.22, 0.26, 0.18],
        "corr_matrix": [[1.0, 0.4, 0.3], [0.4, 1.0, 0.4], [0.3, 0.4, 1.0]],
        "latest_prices": {"FPT": 114500, "MWG": 65200, "VCB": 91500},
        "cash_mode": "fixed_cash",
        "mandated_cash_pct": 0.10,
        "buy_fee_rate": 0.0015,
        "nav_vnd": 1_000_000_000,
    })
    assert r2.status_code == 200
    ex2 = r2.json()["execution"]
    assert ex2["status"] == "ready"
    assert abs((ex2["total_purchase_value"] + ex2["total_buy_fees"] + ex2["cash_remaining"]) - 1_000_000_000.0) <= 1.0
    assert abs(ex2["nav_post_fee"] - (ex2["total_purchase_value"] + ex2["cash_remaining"])) <= 1.0
    assert abs(sum(ex2["actual_weights_post_fee"]) + ex2["actual_cash_weight_post_fee"] - 1.0) < 1e-6

    # Suite 3: Small NAV (< 1 Lot cost) -> 0 shares across all stocks, 0 fee, full cash retained
    r3 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["FPT", "VCB"],
        "expected_returns": [0.20, 0.14],
        "std_devs": [0.22, 0.18],
        "corr_matrix": [[1.0, 0.3], [0.3, 1.0]],
        "latest_prices": {"FPT": 120000, "VCB": 95000},
        "cash_mode": "fixed_cash",
        "mandated_cash_pct": 0.0,
        "nav_vnd": 500_000,
    })
    assert r3.status_code == 200
    ex3 = r3.json()["execution"]
    assert all(o["lots"] == 0 for o in ex3["orders"])
    assert ex3["total_buy_fees"] == 0.0
    assert ex3["cash_remaining"] == 500_000.0

    # Suite 4: 4 stocks with 20% cap -> MUST block with HTTP 400 (NEVER auto-relax to 25%)
    r4 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["FPT", "MWG", "VCB", "HPG"],
        "expected_returns": [0.22, 0.16, 0.14, 0.18],
        "std_devs": [0.22, 0.28, 0.18, 0.25],
        "corr_matrix": [[1.0, 0.4, 0.3, 0.3], [0.4, 1.0, 0.4, 0.4], [0.3, 0.4, 1.0, 0.3], [0.3, 0.4, 0.3, 1.0]],
        "w_min": 0.0,
        "w_max": 0.20,
    })
    assert r4.status_code == 400
    d4 = r4.json()["detail"]
    assert d4["code"] == "max_sum_below_1"
    assert d4["suggestion"]

    # Suite 5: 4 stocks with 25% cap -> singleton domain, Monte Carlo = 1 feasible point
    r5 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["FPT", "MWG", "VCB", "HPG"],
        "expected_returns": [0.22, 0.16, 0.14, 0.18],
        "std_devs": [0.22, 0.28, 0.18, 0.25],
        "corr_matrix": [[1.0, 0.4, 0.3, 0.3], [0.4, 1.0, 0.4, 0.4], [0.3, 0.4, 1.0, 0.3], [0.3, 0.4, 0.3, 1.0]],
        "w_min": 0.0,
        "w_max": 0.25,
    })
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["is_singleton"] is True
    assert len(d5["monte_carlo"]) == 1
    assert all(abs(w - 0.25) < 1e-6 for w in d5["tangency"]["weights"])

    # Suite 6: Manual matrix without prices -> execution disabled_no_prices, zero 50k fabrication
    r6 = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["X1", "X2", "X3"],
        "expected_returns": [0.18, 0.14, 0.12],
        "std_devs": [0.22, 0.18, 0.15],
        "corr_matrix": [[1.0, 0.3, 0.2], [0.3, 1.0, 0.2], [0.2, 0.2, 1.0]],
        "latest_prices": None,
    })
    assert r6.status_code == 200
    d6 = r6.json()
    assert d6["execution"]["status"] == "disabled_no_prices"
    assert all(o["price_vnd"] is None and o["lots"] is None for o in d6["execution"]["orders"])

    # Suite 7: Manual matrix without history -> benchmark unavailable, no fake MDD or scenarios
    assert d6["benchmark_comparison"]["status"] == "unavailable"
    assert d6["stress_testing"]["var_metrics"]["max_drawdown_complete_pct"] is None
    assert d6["stress_testing"]["scenarios"] == []

    # Suite 8: Source & upload isolation via distinct dataset_id + duplicate ticker check
    def _make_price_xlsx(vals_map):
        wb = Workbook()
        ws = wb.active
        ws.title = "Historical_Prices"
        syms = list(vals_map.keys())
        ws.append(["Date"] + syms)
        dates_s = pd.date_range("2025-01-01", periods=len(vals_map[syms[0]]), freq="B")
        for idx_d, dt in enumerate(dates_s):
            ws.append([dt.strftime("%Y-%m-%d")] + [vals_map[s][idx_d] for s in syms])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    up_a_bytes = _make_price_xlsx({
        "AAA": [10000 + i * 50 for i in range(45)],
        "BBB": [20000 + i * 30 for i in range(45)],
    })
    up_b_bytes = _make_price_xlsx({
        "CCC": [30000 + i * 80 for i in range(45)],
        "DDD": [40000 + (i % 5) * 40 for i in range(45)],
    })
    resp_a = client.post("/api/upload-excel", files={"file": ("a.xlsx", up_a_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    resp_b = client.post("/api/upload-excel", files={"file": ("b.xlsx", up_b_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp_a.status_code == 200 and resp_b.status_code == 200
    id_a = resp_a.json()["dataset_id"]
    id_b = resp_b.json()["dataset_id"]
    assert id_a != id_b

    opt_a = client.post("/api/optimize", json={"input_mode": "uploaded_prices", "dataset_id": id_a, "symbols": ["AAA", "BBB"]})
    assert opt_a.status_code == 200
    assert opt_a.json()["symbols"] == ["AAA", "BBB"]

    dup_err = client.post("/api/optimize", json={
        "input_mode": "manual_matrix",
        "symbols": ["FPT", "FPT"],
        "expected_returns": [0.2, 0.2],
        "std_devs": [0.2, 0.2],
        "corr_matrix": [[1.0, 0.5], [0.5, 1.0]],
    })
    assert dup_err.status_code == 400

    # Suite 9: Snapshot fidelity via run_id (Export reflects committed snapshot 1 even after snapshot 2 ran, 404 on unknown)
    run_id_1 = d1["run_id"]
    exp_snap1 = client.post("/api/export-excel", json={"run_id": run_id_1, "lang": "en"})
    assert exp_snap1.status_code == 200
    wb_s1 = load_workbook(io.BytesIO(exp_snap1.content), data_only=True)
    assert run_id_1 in str(wb_s1["01_Executive_Summary"]["B5"].value)
    assert str(wb_s1["01_Executive_Summary"]["A20"].value) == "A1"

    missing_snap = client.post("/api/export-excel", json={"run_id": "nonexistent_run_id_999"})
    assert missing_snap.status_code == 404

    # Suite 10: Benchmark Attribution tab in Manual Matrix stays isolated (unavailable)
    r_bm_man = client.post("/api/benchmark-attribution", json={
        "symbols": ["X1", "X2"],
        "w_tangency": [0.5, 0.5],
        "tangency_return": 0.16,
        "tangency_volatility": 0.18,
        "tangency_sharpe": 0.6,
        "input_mode": "manual_matrix",
    })
    assert r_bm_man.status_code == 200
    assert r_bm_man.json()["status"] == "unavailable"


def test_bloomberg_benchmark_attribution_and_fullscreen_ux():
    """Verify Benchmark Attribution endpoint, single-zoom modal, Bloomberg pills, and v2.5.0 assets."""
    bm_req = BenchmarkAttributionRequest(
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM"],
        w_tangency=[0.25, 0.15, 0.20, 0.20, 0.20],
        tangency_return=0.185,
        tangency_volatility=0.21,
        tangency_sharpe=0.667,
        rf=0.045,
        benchmark_symbol="VN30",
        benchmark_range="6m",
        use_adjusted_close=True,
        input_mode="live_market",
    )
    res_bm = api_benchmark_attribution(bm_req)
    assert res_bm["status"] == "available"
    assert res_bm["benchmark_symbol"] == "VN30"
    assert res_bm["benchmark_range"] == "6M"
    assert abs(res_bm["cumulative_series"]["portfolio_base100"][0] - 100.0) < 1e-6

    html_text = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js_text = (PROJECT_ROOT / "static" / "textbook_mvo.js").read_text(encoding="utf-8")
    i18n_text = (PROJECT_ROOT / "static" / "i18n.js").read_text(encoding="utf-8")

    # No Markowits typo, no TT 98/2020 regulatory claim, default lang="vi"
    assert "Markowits" not in html_text
    assert "TT 98/2020" not in html_text
    assert '<html lang="vi">' in html_text
    assert "hayinsights-quick-chips" not in html_text

    # Single zoom button per chart (exactly 1 openChartFullscreen for each chart key)
    assert html_text.count("openChartFullscreen('frontier')") == 1
    assert html_text.count("openChartFullscreen('weights')") == 1
    assert html_text.count("openChartFullscreen('benchmark')") == 1

    # Accessible dialogs & form labels
    assert 'role="dialog"' in html_text
    assert 'aria-modal="true"' in html_text
    for inp_id in ("inp-ticker-search", "inp-rf", "inp-nav", "inp-buy-fee", "rng-risk-a", "rng-w-min", "rng-w-max"):
        assert f'for="{inp_id}"' in html_text, f"Missing <label for='{inp_id}'> in index.html"

    # Required Bloomberg pills & v2.5.0 cache-busting tags
    for hz in ("6m", "1y", "3y", "5y", "ytd", "max"):
        assert f'id="bm-pill-hz-{hz}"' in html_text
    assert 'id="bm-pill-idx-vnindex"' in html_text
    assert 'id="bm-pill-idx-vn30"' in html_text
    for kpi_id in ("bm-kpi-alpha", "bm-kpi-beta", "bm-kpi-ir", "bm-kpi-te", "bm-kpi-corr"):
        assert f'id="{kpi_id}"' in html_text
    assert "i18n.js?v=2.5.0" in html_text
    assert "textbook_mvo.js?v=2.5.0" in html_text

    # DOM ID & onclick handler contract
    html_ids = set(re.findall(r'id="([^"]+)"', html_text))
    js_static_ids = set(re.findall(r"getElementById\('([^'$]+)'\)", js_text))
    missing_ids = js_static_ids - html_ids
    assert not missing_ids, f"Missing DOM IDs in index.html: {missing_ids}"

    for fn in (
        "openChartFullscreen",
        "closeChartFullscreen",
        "resetFullscreenChartPlot",
        "setBenchmarkHorizon",
        "setBenchmarkIndex",
        "exportCurrentPriceData",
        "exportCurrentMatrixData",
        "setLanguage",
        "setRiskReportBasis",
        "toggleCap20Preset",
    ):
        assert f"window.{fn} = {fn}" in js_text, f"Missing window export for {fn}"

    # Verify MVO_I18N VI vs EN exact key parity via pure-Python Esprima AST traversal
    import esprima
    tree = esprima.parseScript(i18n_text)
    lang_keys = {}
    def _walk(node):
        if hasattr(node, "type"):
            if node.type == "VariableDeclarator" and getattr(node.id, "name", "") == "MVO_I18N":
                for prop in node.init.properties:
                    lname = getattr(prop.key, "name", None) or getattr(prop.key, "value", None)
                    lang_keys[lname] = {
                        (getattr(p.key, "value", None) or getattr(p.key, "name", None))
                        for p in prop.value.properties
                    }
            for k in vars(node).values():
                if isinstance(k, list):
                    for item in k:
                        _walk(item)
                elif hasattr(k, "type"):
                    _walk(k)
    _walk(tree)
    assert "vi" in lang_keys and "en" in lang_keys
    assert lang_keys["vi"] == lang_keys["en"], f"VI vs EN i18n key mismatch: {lang_keys['vi'] ^ lang_keys['en']}"
    html_i18n_keys = set(re.findall(r'data-i18n(?:-[a-z]+)?="([^"]+)"', html_text))
    missing_html_keys = html_i18n_keys - lang_keys["vi"]
    assert not missing_html_keys, f"Missing i18n keys referenced in index.html: {missing_html_keys}"
    js_i18n_keys = set(re.findall(r"tr\('([^']+)'", js_text))
    missing_js_keys = js_i18n_keys - lang_keys["vi"]
    assert not missing_js_keys, f"Missing i18n keys referenced in textbook_mvo.js: {missing_js_keys}"


def test_javascript_ast_syntax_and_onclick_handlers():
    """Verify full JavaScript syntax validity (i18n.js & textbook_mvo.js) and onclick bindings."""
    html_text = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js_text = (PROJECT_ROOT / "static" / "textbook_mvo.js").read_text(encoding="utf-8")
    i18n_text = (PROJECT_ROOT / "static" / "i18n.js").read_text(encoding="utf-8")

    assert js_text.count("{") == js_text.count("}")
    assert js_text.count("(") == js_text.count(")")
    assert js_text.count("[") == js_text.count("]")

    import esprima
    for src in (i18n_text, js_text):
        es6 = re.sub(r"(\d)_(\d)", r"\1\2", src)
        es6 = es6.replace("?.", ".").replace("??", "||")
        tree = esprima.parseScript(es6)
        assert len(tree.body) >= 1

    onclicks = re.findall(r'onclick="([^"]+)"', html_text)
    for oc in onclicks:
        assert oc.count("(") == oc.count(")"), f"Unbalanced onclick: {oc}"
        for fn in re.findall(r"([a-zA-Z0-9_]+)\s*\(", oc):
            assert f"function {fn}" in js_text or f"window.{fn}" in js_text, f"Missing JS function: {fn}"


if __name__ == "__main__":
    suites = [
        ("1. Merton (1972) Closed-Form Matrix Identities", test_merton_closed_form_identities),
        ("2. Long-Only QP Constraints on Real Market Data", test_long_only_qp_constraints),
        ("3. Investor Risk Profiling Quiz Mapping & Validation", test_risk_profiler_quiz),
        ("4. Excel Template Generation & Upload Roundtrip", test_template_and_upload_roundtrip),
        ("5. 8-Sheet Master Institutional Excel Export", test_institutional_excel_export_8_sheets),
        ("6. HayInsights Live API Multi-Exchange Integration", test_hayinsights_live_api_integration),
        ("7. Bounded QP, Fixed Cash & Bounded Monte Carlo", test_bounded_qp_and_fixed_cash_no_auto_relax),
        ("8. Benchmark Base=100 Attribution & Dual-Basis VaR/ES", test_benchmark_and_stress_testing_engine),
        ("9. Active Price & Matrix Exports + Benchmark Horizons", test_live_price_and_matrix_exports_and_benchmark_horizons),
        ("10. Independent Math Edge Cases (Singular, Zero Excess, Quantile, Rolling 21d)", test_math_edge_cases_independent),
        ("11. Ten Mandatory FastAPI End-to-End Integration Suites", test_ten_end_to_end_integration_suites),
        ("12. Frontend Accessibility, VI/EN Parity & Single-Zoom Modal UX", test_bloomberg_benchmark_attribution_and_fullscreen_ux),
        ("13. JavaScript Esprima AST Syntax & Onclick Binding Guard", test_javascript_ast_syntax_and_onclick_handlers),
    ]
    print(f"Running Markowitz Portfolio Optimization Verification Suite ({len(suites)} Suites)...")
    for label, fn in suites:
        fn()
        print(f"  [PASS] {label}")
    print(f"ALL {len(suites)} VERIFICATION SUITES PASSED SUCCESSFULLY!")
