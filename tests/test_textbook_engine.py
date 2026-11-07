"""
Comprehensive Verification Test Suite for Pure Textbook MVO Application.
Tests:
1. Merton (1972) Closed-Form Matrix Solution identities (w_gmv, w_tangency, scalars A, B, C, D)
2. Long-Only Quadratic Programming constraints (w_i >= 0, sum = 1)
3. 252-Session Annualization Convention
4. Investor Risk Profiling Quiz mapping (score 4..16 -> A in [1.2, 8.0])
5. Template Generator & Excel Upload round-trip
6. 6-Sheet Institutional Excel Report Exporter verification
7. FastAPI Endpoints end-to-end
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
    OptimizeRequest,
    QuizSubmission,
    api_evaluate_quiz,
    api_export_excel,
    api_get_presets,
    api_optimize,
    api_quote_ticker,
    api_search_tickers,
)
from engine import data_loader, excel_exporter, risk_profiler, template_generator, textbook_math


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
    """Verify that Long-Only QP strictly satisfies w_i >= 0 and sum(w_i) = 1."""
    df = data_loader.get_market_price_dataframe(["FPT", "MWG", "VCB", "HPG"], n_sessions=252)
    moments = textbook_math.compute_moments_from_prices(df, trading_days=252)
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
    assert parsed["symbols"] == ["FPT", "MWG", "VCB", "HPG"]
    assert len(parsed["mu"]) == 4

    prices_bytes = template_generator.generate_input_template_xlsx(mode="prices")
    parsed_p = data_loader.parse_uploaded_file(prices_bytes, "prices.xlsx")
    assert len(parsed_p["symbols"]) == 4


def test_institutional_excel_export_6_sheets():
    """Verify the exported Excel workbook contains all 6 sheets and live formulas."""
    req = OptimizeRequest(
        input_mode="market",
        symbols=["FPT", "MWG", "VCB", "HPG"],
        rf=0.045,
        risk_aversion_A=3.0,
        allow_short=True,
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
    ]
    assert wb.sheetnames == expected_sheets
    # Check live formula in 01_Executive_Summary
    ws1 = wb["01_Executive_Summary"]
    assert str(ws1["D25"].value).startswith("=SUM(")


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
    """Verify every DOM ID referenced in textbook_mvo.js exists in index.html and JSON contract matches."""
    import re

    html_text = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js_text = (PROJECT_ROOT / "static" / "textbook_mvo.js").read_text(encoding="utf-8")

    html_ids = set(re.findall(r'id="([^"]+)"', html_text))
    js_static_ids = set(re.findall(r"getElementById\('([^'$]+)'\)", js_text))
    missing_ids = js_static_ids - html_ids
    assert not missing_ids, f"Missing DOM IDs in index.html: {missing_ids}"

    # Verify JSON response schema matches frontend expectations
    res = api_optimize(OptimizeRequest())
    comp = res["complete_portfolio"]
    for key in ["y_star_risky_weight", "w_rf_weight", "asset_weights", "expected_return", "volatility", "utility_score", "cal_line", "indifference_curve"]:
        assert key in comp and comp[key] is not None, f"Missing key in complete_portfolio: {key}"

    assert "return" in res["frontier"][0] and "volatility" in res["frontier"][0]
    assert "return" in res["monte_carlo"][0] and "volatility" in res["monte_carlo"][0] and "sharpe" in res["monte_carlo"][0]


def test_bounded_qp_and_mandated_cash():
    """Verify Weight Bounds (Circular 98 max 20%, min floor, feasibility guard) and Mandated Cash %NAV."""
    # 1. 6 stocks with Circular 98 cap (w_max = 0.20, w_min = 0.05)
    req_bounded = OptimizeRequest(
        input_mode="market",
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
        input_mode="market",
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
        cash_mode="mandated",
        mandated_cash_pct=0.10,
        nav_vnd=1_000_000_000.0,
    )
    res = api_optimize(req)
    bm = res["benchmark_comparison"]
    assert bm["benchmark_symbol"] == "VN30"
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
        assert sc["post_shock_nav_vnd"] < 1_000_000_000.0
        # Because 10% cash buffer is held, cash_protection_vnd must be > 0
        assert sc["cash_protection_vnd"] > 0


if __name__ == "__main__":
    test_merton_closed_form_identities()
    print("[PASS] 1. Merton (1972) Closed-Form Analytical Matrix Identities")
    test_long_only_qp_constraints()
    print("[PASS] 2. Long-Only Quadratic Programming Constraints (w_i >= 0, sum = 1)")
    test_risk_profiler_quiz()
    print("[PASS] 3. Investor Risk Profiling Quiz (4 Questions -> A in [1.2, 8.0])")
    test_template_and_upload_roundtrip()
    print("[PASS] 4. Excel Input Template Generation & Upload Parser Roundtrip")
    test_institutional_excel_export_6_sheets()
    print("[PASS] 5. 6-Sheet Institutional Excel Report Exporter & API Verification")
    test_hayinsights_live_api_integration()
    print("[PASS] 6. Live HayInsights API Integration (VNSC Adjusted Close -> MVO)")
    test_frontend_dom_and_json_contract()
    print("[PASS] 7. Frontend DOM IDs & JSON Schema Contract Verification")
    test_bounded_qp_and_mandated_cash()
    print("[PASS] 8. Institutional Weight Bounds (Circular 98 Cap) & Mandated Cash %NAV")
    test_benchmark_and_stress_testing_engine()
    print("[PASS] 9. Benchmark Comparison (VN-Index/VN30) & Tail-Risk Stress Testing (VaR/CVaR)")
    print("\nALL 9 TEST SUITES PASSED 100%!")
