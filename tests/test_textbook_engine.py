"""
Comprehensive Verification Test Suite for Portfolio Optimization by Khim (v2.4 Institutional Edition).
Tests:
1. Merton (1972) Closed-Form Matrix Solution identities (w_gmv, w_tangency, scalars A, B, C, D)
2. Long-Only Quadratic Programming constraints (w_i >= 0, sum = 1) on real market prices
3. 252-Session Annualization Convention
4. Investor Risk Profiling Quiz mapping (score 4..16 -> A in [1.2, 8.0])
5. Template Generator & Excel Upload round-trip
6. 8-Sheet Institutional Excel Report Exporter verification (including Benchmark Scorecard & Stress Testing VaR)
7. HayInsights Live API multi-exchange integration
8. Frontend DOM & JSON contract validation (confirming Quick Select removal & Benchmark Horizon controls)
9. Bounded QP (Circular 98/2020) & Mandated Cash %NAV
10. Active Input Data Exporters (`Export Price Data` with Trading Volume & `Export Matrix Data`) + Benchmark Horizons + Roundtrip Upload
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from openpyxl import load_workbook

from app import (
    BenchmarkAttributionRequest,
    OptimizeRequest,
    QuizSubmission,
    api_benchmark_attribution,
    api_evaluate_quiz,
    api_export_excel,
    api_export_matrix,
    api_export_prices,
    api_get_presets,
    api_optimize,
    api_quote_ticker,
    api_search_tickers,
    app,
)
from engine import data_loader, hayinsights_client, risk_profiler, template_generator, textbook_math


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

    # Identity: E(R_gmv) == A / C and Var(R_gmv) == 1 / C
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
    """Verify 4-question quiz scoring and mapping to Risk Aversion A."""
    conservative = risk_profiler.evaluate_risk_profile([1, 1, 1, 1])
    assert conservative["total_score"] == 4
    assert conservative["risk_aversion_A"] == 8.0

    aggressive = risk_profiler.evaluate_risk_profile([4, 4, 4, 4])
    assert aggressive["total_score"] == 16
    assert aggressive["risk_aversion_A"] == 1.2


def test_template_and_upload_roundtrip():
    """Verify generating input Excel template and parsing it back."""
    xlsx_bytes = template_generator.generate_input_template_xlsx(mode="parameters")
    parsed = data_loader.parse_uploaded_file(xlsx_bytes, "template.xlsx")
    assert len(parsed["symbols"]) >= 3
    assert len(parsed["mu"]) == len(parsed["symbols"])

    prices_bytes = template_generator.generate_input_template_xlsx(mode="prices")
    parsed_p = data_loader.parse_uploaded_file(prices_bytes, "prices.xlsx")
    assert len(parsed_p["symbols"]) >= 3


def test_institutional_excel_export_8_sheets():
    """Verify the exported Master Excel workbook contains all 8 sheets including Benchmark & Stress Testing."""
    req = OptimizeRequest(
        input_mode="hayinsights",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM"],
        rf=0.045,
        risk_aversion_A=3.0,
        allow_short=True,
        benchmark_symbol="VNINDEX",
        benchmark_range="1y",
        nav_vnd=1_000_000_000.0,
    )
    opt_res = api_optimize(req)
    assert opt_res["status"] == "success"
    assert len(opt_res["frontier"]) == 50

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
    # Check live formula in 01_Executive_Summary (5 symbols -> row 26)
    ws1 = wb["01_Executive_Summary"]
    assert str(ws1["D26"].value).startswith("=SUM(")
    # Check Sheet 7 & Sheet 8 contents
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

    # Test 1-2 character prefix search
    res_vc = api_search_tickers(q="VC")
    vc_syms = [r["symbol"] for r in res_vc["results"]]
    assert "VCB" in vc_syms and "VCI" in vc_syms and "VCG" in vc_syms

    # Test live quote for a non-preset stock (DGC)
    quote_dgc = api_quote_ticker("DGC")
    assert quote_dgc["valid"] is True
    assert quote_dgc["latest_price"] > 0

    # Test MVO optimization with non-preset stocks across HOSE, HNX, UPCoM
    req = OptimizeRequest(
        input_mode="hayinsights",
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
    assert opt_res["data_meta"]["formula_version"] == "vnsc-adjusted-close-v1"
    assert abs(sum(opt_res["tangency"]["weights"]) - 1.0) < 1e-6


def test_frontend_dom_and_json_contract():
    """Verify every DOM ID referenced in textbook_mvo.js exists in index.html and Quick Select is removed."""
    import re

    html_text = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js_text = (PROJECT_ROOT / "static" / "textbook_mvo.js").read_text(encoding="utf-8")

    # Confirm Quick Select is completely removed
    assert "hayinsights-quick-chips" not in html_text
    assert "hayinsights-quick-chips" not in js_text

    html_ids = set(re.findall(r'id="([^"]+)"', html_text))
    js_static_ids = set(re.findall(r"getElementById\('([^'$]+)'\)", js_text))
    missing_ids = js_static_ids - html_ids
    assert not missing_ids, f"Missing DOM IDs in index.html: {missing_ids}"

    # Verify JSON response schema matches frontend expectations
    res = api_optimize(OptimizeRequest())
    comp = res["complete_portfolio"]
    for key in ["y_star_risky_weight", "w_rf_weight", "asset_weights", "expected_return", "volatility", "utility_score", "cal_line", "indifference_curve"]:
        assert key in comp and comp[key] is not None, f"Missing key in complete_portfolio: {key}"


def test_bounded_qp_and_mandated_cash():
    """Verify Weight Bounds (Circular 98 max 20%, min floor, feasibility guard) and Mandated Cash %NAV."""
    req_bounded = OptimizeRequest(
        input_mode="hayinsights",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM", "SSI"],
        w_min=0.05,
        w_max=0.20,
        cash_mode="mandated",
        mandated_cash_pct=0.15,
        nav_vnd=2_000_000_000.0,
    )
    res = api_optimize(req_bounded)
    w_tan = res["tangency"]["weights"]
    w_gmv = res["gmv"]["weights"]
    assert abs(sum(w_tan) - 1.0) < 1e-5
    assert abs(sum(w_gmv) - 1.0) < 1e-5
    for w in w_tan:
        assert 0.05 - 1e-4 <= w <= 0.20 + 1e-4, f"Tangency weight {w} violated [0.05, 0.20] bounds"
    for w in w_gmv:
        assert 0.05 - 1e-4 <= w <= 0.20 + 1e-4, f"GMV weight {w} violated [0.05, 0.20] bounds"

    # Verify Mandated Cash (15% cash -> 85% risky equity)
    comp = res["complete_portfolio"]
    assert comp["cash_mode"] == "mandated"
    assert abs(comp["w_rf_weight"] - 0.15) < 1e-6
    assert abs(comp["y_star_risky_weight"] - 0.85) < 1e-6
    assert abs(sum(comp["asset_weights"]) - 0.85) < 1e-5

    # 2. Feasibility Guard: 4 stocks with 20% cap (4 * 20% = 80% < 100%) -> auto-adjusts to 25%
    req_infeasible = OptimizeRequest(
        input_mode="hayinsights",
        symbols=["FPT", "MWG", "VCB", "HPG"],
        w_min=0.0,
        w_max=0.20,
    )
    res_inf = api_optimize(req_infeasible)
    assert res_inf["bounds_adjusted_note"] is not None
    assert abs(res_inf["w_max"] - 0.25) < 1e-3


def test_benchmark_and_stress_testing_engine():
    """Verify Benchmark Comparison (VNINDEX / VN30) and Stress Testing / VaR metrics."""
    req = OptimizeRequest(
        input_mode="hayinsights",
        symbols=["FPT", "MWG", "VCB", "HPG", "VNM"],
        benchmark_symbol="VN30",
        benchmark_range="1y",
        cash_mode="mandated",
        mandated_cash_pct=0.10,
        nav_vnd=1_000_000_000.0,
    )
    res = api_optimize(req)
    bm = res["benchmark_comparison"]
    assert bm["benchmark_symbol"] == "VN30"
    assert bm["benchmark_range"] == "1Y"
    for k in ["benchmark_return", "benchmark_volatility", "beta", "jensen_alpha", "tracking_error", "information_ratio"]:
        assert k in bm and bm[k] is not None

    st = res["stress_testing"]
    vm = st["var_metrics"]
    assert vm["var_95_1d_pct"] > 0
    assert vm["var_99_1d_pct"] >= vm["var_95_1d_pct"]
    assert vm["cvar_95_1d_pct"] >= vm["var_95_1d_pct"]
    assert len(st["scenarios"]) == 4
    for sc in st["scenarios"]:
        assert sc["estimated_loss_vnd"] > 0


def test_live_price_and_matrix_exports_and_benchmark_horizons():
    """
    Test Suite 10:
    1. Export Live Price Data (4 sheets including Trading_Volume) & Roundtrip Upload back into data_loader
    2. Export Live Parameter Matrix (3 sheets) & Roundtrip Upload back into data_loader
    3. Multi-Horizon Benchmark Comparison (6m, 1y, 3y, 5y, ytd, max)
    """
    syms = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    req = OptimizeRequest(
        input_mode="hayinsights",
        symbols=syms,
        hayinsights_range="1y",
        use_adjusted_close=True,
        benchmark_symbol="VNINDEX",
        benchmark_range="6m",
    )
    opt_res = api_optimize(req)
    assert opt_res["benchmark_comparison"]["benchmark_range"] == "6M"

    # 1. Test Export Price Data (with Trading Volume)
    res_prices = api_export_prices(req)
    assert res_prices.status_code == 200
    assert "Portfolio_Prices_5Assets_1Y_" in res_prices.headers.get("content-disposition", "")

    wb_p = load_workbook(io.BytesIO(res_prices.body), data_only=True)
    assert wb_p.sheetnames == ["Historical_Prices", "Trading_Volume", "Daily_Returns", "Universe_Summary"]
    ws_vol = wb_p["Trading_Volume"]
    assert ws_vol["A1"].value == "Date"
    assert ws_vol["B1"].value == "FPT"
    assert float(ws_vol["B2"].value) > 0  # Real trading volume

    # Roundtrip Upload of exported Price file
    roundtrip_p = data_loader.parse_uploaded_file(res_prices.body, "Portfolio_Prices_5Assets.xlsx")
    assert roundtrip_p["symbols"] == syms
    assert roundtrip_p["volumes_df"] is not None
    assert np.allclose(roundtrip_p["mu"], opt_res["mu"], atol=1e-4)
    assert np.allclose(roundtrip_p["std"], opt_res["std"], atol=1e-4)

    # 2. Test Export Matrix Data
    res_mat = api_export_matrix(req)
    assert res_mat.status_code == 200
    assert "Portfolio_Matrix_5Assets_" in res_mat.headers.get("content-disposition", "")

    wb_m = load_workbook(io.BytesIO(res_mat.body), data_only=True)
    assert wb_m.sheetnames == ["Parameters", "Covariance_Matrix", "Asset_Statistics"]

    # Roundtrip Upload of exported Matrix file
    roundtrip_m = data_loader.parse_uploaded_file(res_mat.body, "Portfolio_Matrix_5Assets.xlsx")
    assert roundtrip_m["symbols"] == syms
    assert np.allclose(roundtrip_m["mu"], opt_res["mu"], atol=1e-5)
    assert np.allclose(roundtrip_m["std"], opt_res["std"], atol=1e-5)
    assert np.allclose(roundtrip_m["corr"], opt_res["corr"], atol=1e-4)

    # 3. Verify Benchmark Horizons ('ytd' and '3y')
    for hz in ("ytd", "3y", "max"):
        req_hz = OptimizeRequest(
            input_mode="hayinsights",
            symbols=["FPT", "VCB", "HPG"],
            hayinsights_range="1y",
            benchmark_symbol="VNINDEX",
            benchmark_range=hz,
        )
        res_hz = api_optimize(req_hz)
        assert res_hz["benchmark_comparison"]["benchmark_range"] == hz.upper()
        assert len(res_hz["benchmark_comparison"]["cumulative_series"]["dates"]) >= 10


def test_bloomberg_benchmark_attribution_and_fullscreen_ux():
    """Verify dedicated Benchmark Attribution endpoint, Bloomberg Terminal quick pills, and Fullscreen modal."""
    # 1. Test dedicated Benchmark Attribution endpoint
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
    )
    res_bm = api_benchmark_attribution(bm_req)
    assert res_bm["benchmark_symbol"] == "VN30"
    assert res_bm["benchmark_range"] == "6M"
    assert "beta" in res_bm and res_bm["beta"] is not None
    assert "active_return" in res_bm
    assert "tracking_error" in res_bm
    assert "information_ratio" in res_bm
    assert "correlation" in res_bm
    assert "r_squared" in res_bm
    assert len(res_bm["cumulative_series"]["dates"]) > 0
    assert len(res_bm["cumulative_series"]["portfolio_base100"]) == len(res_bm["cumulative_series"]["dates"])
    assert len(res_bm["cumulative_series"]["benchmark_base100"]) == len(res_bm["cumulative_series"]["dates"])
    assert 50.0 < res_bm["cumulative_series"]["portfolio_base100"][0] < 150.0
    assert 50.0 < res_bm["cumulative_series"]["benchmark_base100"][0] < 150.0

    # 2. Test Fullscreen Modal & Bloomberg Terminal DOM Elements in index.html
    html_path = PROJECT_ROOT / "static" / "index.html"
    html_text = html_path.read_text(encoding="utf-8")
    assert 'id="modal-chart-fullscreen"' in html_text, "Missing modal-chart-fullscreen in index.html"
    assert 'id="chart-fullscreen-plot"' in html_text, "Missing chart-fullscreen-plot in index.html"
    assert "openChartFullscreen('frontier')" in html_text, "Missing openChartFullscreen for frontier"
    assert "openChartFullscreen('weights')" in html_text, "Missing openChartFullscreen for weights"
    assert "openChartFullscreen('benchmark')" in html_text, "Missing openChartFullscreen for benchmark"

    # Bloomberg Quick Pills in tab-panel-benchmark
    for hz in ("6m", "1y", "3y", "5y", "ytd", "max"):
        assert f'id="bm-pill-hz-{hz}"' in html_text, f"Missing bm-pill-hz-{hz} in index.html"
    assert 'id="bm-pill-idx-vnindex"' in html_text
    assert 'id="bm-pill-idx-vn30"' in html_text

    # Terminal 5-KPI Strip
    for kpi_id in ("bm-kpi-alpha", "bm-kpi-beta", "bm-kpi-ir", "bm-kpi-te", "bm-kpi-corr"):
        assert f'id="{kpi_id}"' in html_text, f"Missing {kpi_id} in index.html"

    # Cache busting script tag
    assert 'textbook_mvo.js?v=2.4.3' in html_text, "Missing cache-busting v=2.4.3 script tag"

    # 3. Test textbook_mvo.js functions and window exports
    js_path = PROJECT_ROOT / "static" / "textbook_mvo.js"
    js_text = js_path.read_text(encoding="utf-8")
    for fn in ("openChartFullscreen", "closeChartFullscreen", "resetFullscreenChartPlot", "setBenchmarkHorizon", "setBenchmarkIndex", "exportCurrentPriceData", "exportCurrentMatrixData"):
        assert f"window.{fn} = {fn}" in js_text, f"Missing window export for {fn}"


if __name__ == "__main__":
    print("Running Portfolio Optimization by Khim Verification Suite (11 Suites)...")
    test_merton_closed_form_identities()
    print("  [PASS] 1. Merton (1972) Closed-Form Matrix Identities (A, B, C, D, Sigma^-1)")
    test_long_only_qp_constraints()
    print("  [PASS] 2. Long-Only Quadratic Programming (SLSQP) Constraints on Real Data")
    test_risk_profiler_quiz()
    print("  [PASS] 3. Investor Risk Profiling Quiz -> Risk Aversion A")
    test_template_and_upload_roundtrip()
    print("  [PASS] 4. Excel Template Generation & Upload Parser Roundtrip")
    test_institutional_excel_export_8_sheets()
    print("  [PASS] 5. 8-Sheet Master Institutional Excel Export (with Benchmark & Stress Testing)")
    test_hayinsights_live_api_integration()
    print("  [PASS] 6. HayInsights Live API Multi-Exchange (HOSE/HNX/UPCoM) Integration")
    test_frontend_dom_and_json_contract()
    print("  [PASS] 7. Frontend DOM IDs (Quick Select Removed) & JSON Response Contract")
    test_bounded_qp_and_mandated_cash()
    print("  [PASS] 8. Weight Bounds (Circular 98/2020) & Mandated Cash Allocation")
    test_benchmark_and_stress_testing_engine()
    print("  [PASS] 9. Benchmark Comparison (VN-Index / VN30) & Tail-Risk Stress Testing (VaR/CVaR)")
    test_live_price_and_matrix_exports_and_benchmark_horizons()
    print("  [PASS] 10. Active Price (with Volume) & Matrix Exports + Benchmark Horizons + Roundtrip")
    test_bloomberg_benchmark_attribution_and_fullscreen_ux()
    print("  [PASS] 11. Bloomberg Terminal Benchmark UX, Fullscreen HD Modal & Cache-Busting")
    print("ALL 11 VERIFICATION SUITES PASSED SUCCESSFULLY!")
