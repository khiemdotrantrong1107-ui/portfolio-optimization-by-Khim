"""
FastAPI Backend for Pure Textbook MVO & Institutional Portfolio Construction Workbench.
100% Real Market Data & User Upload Architecture (Zero Synthetic Fallback).
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import (
    benchmark_engine,
    data_exporter,
    data_loader,
    execution_engine,
    hayinsights_client,
    risk_profiler,
    template_generator,
    textbook_math,
    excel_exporter,
)

app = FastAPI(
    title="Portfolio Optimization by Khim — Quantitative MVO Workbench",
    version="2.5.0",
    description="Hệ thống Tối ưu hóa Danh mục Đầu tư Mean-Variance (Markowitz 1952 - Merton 1972) nhất quán ràng buộc, kế toán thực thi và minh bạch mô hình.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

MAX_SNAPSHOTS = 50
_SNAPSHOT_STORE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_SNAPSHOT_DATAFRAMES: OrderedDict[str, dict[str, Any]] = OrderedDict()


class QuizSubmission(BaseModel):
    scores: list[int]


class BenchmarkAttributionRequest(BaseModel):
    symbols: list[str] = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    w_tangency: list[float]
    tangency_return: float
    tangency_volatility: float
    tangency_sharpe: float
    rf: float = 0.045
    benchmark_symbol: str = "VNINDEX"
    benchmark_range: str = "1y"
    optimization_range: str | None = None
    use_adjusted_close: bool = True
    input_mode: str = "live_market"
    dataset_id: str | None = None
    run_id: str | None = None


class OptimizeRequest(BaseModel):
    input_mode: str = "live_market"  # "live_market" ("hayinsights"), "uploaded_prices", "manual_matrix" ("manual")
    dataset_id: str | None = None
    run_id: str | None = None
    symbols: list[str] = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    hayinsights_range: str = "1y"
    use_adjusted_close: bool = True
    expected_returns: list[float] | None = None
    std_devs: list[float] | None = None
    corr_matrix: list[list[float]] | None = None
    latest_prices: dict[str, float | None] | None = None
    rf: float = 0.045
    risk_aversion_gamma: float | None = None
    risk_aversion_A: float = 3.0
    allow_short: bool = False
    w_min: float = 0.0
    w_max: float = 1.0
    cash_mode: str = "utility_no_leverage"  # "utility_no_leverage" ("bkm") or "fixed_cash" ("mandated")
    mandated_cash_pct: float = 0.10
    benchmark_symbol: str = "VNINDEX"  # "VNINDEX" or "VN30"
    benchmark_range: str = "1y"  # "6m", "1y", "3y", "5y", "ytd", "max"
    nav_vnd: float = 1_000_000_000.0
    n_monte_carlo: int = 2500
    lot_size: int = 100
    buy_fee_rate: float = 0.0015
    risk_report_basis: str = "target_complete"
    lang: str = "vi"


def _normalize_input_mode(raw_mode: str | None) -> str:
    m = (raw_mode or "live_market").strip().lower()
    if m in ("live_market", "hayinsights", "live"):
        return "live_market"
    if m in ("uploaded_prices", "upload_prices", "uploaded"):
        return "uploaded_prices"
    if m in ("manual_matrix", "manual", "uploaded_parameters"):
        return "manual_matrix"
    return "live_market"


def _save_snapshot(run_id: str, analysis: dict[str, Any], df_bundle: dict[str, Any]) -> None:
    _SNAPSHOT_STORE[run_id] = analysis
    _SNAPSHOT_STORE.move_to_end(run_id)
    _SNAPSHOT_DATAFRAMES[run_id] = df_bundle
    _SNAPSHOT_DATAFRAMES.move_to_end(run_id)
    while len(_SNAPSHOT_STORE) > MAX_SNAPSHOTS:
        old_id, _ = _SNAPSHOT_STORE.popitem(last=False)
        _SNAPSHOT_DATAFRAMES.pop(old_id, None)


def _get_snapshot_or_404(run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    snap = _SNAPSHOT_STORE.get(run_id)
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"Phiên tính toán '{run_id}' không còn trong bộ nhớ đệm. Vui lòng bấm Run Optimization lại.",
        )
    _SNAPSHOT_STORE.move_to_end(run_id)
    if run_id in _SNAPSHOT_DATAFRAMES:
        _SNAPSHOT_DATAFRAMES.move_to_end(run_id)
    return snap, _SNAPSHOT_DATAFRAMES.get(run_id, {})


def _build_full_analysis(req: OptimizeRequest) -> dict[str, Any]:
    mode_canon = _normalize_input_mode(req.input_mode)
    clean_req_syms = [str(s).strip().upper() for s in req.symbols if str(s).strip()]
    gamma_val = float(req.risk_aversion_gamma if req.risk_aversion_gamma is not None else req.risk_aversion_A)

    # Check duplicate tickers explicitly for all modes
    seen_syms: set[str] = set()
    dups: list[str] = []
    for sym in clean_req_syms:
        if sym in seen_syms and sym not in dups:
            dups.append(sym)
        seen_syms.add(sym)
    if dups:
        raise ValueError(f"Danh sách mã cổ phiếu bị trùng lặp: {', '.join(dups)}. Vui lòng loại bỏ mã trùng.")
    if len(clean_req_syms) < 2:
        raise ValueError("Vui lòng chọn hoặc nhập tối thiểu 2 mã cổ phiếu hợp lệ để tối ưu hóa.")

    df_prices_raw_bundle: Any = None
    df_volumes_bundle: Any = None

    if mode_canon == "uploaded_prices":
        up_ds = data_loader.get_uploaded_dataset(req.dataset_id)
        if not up_ds or up_ds.get("df_prices") is None:
            raise ValueError(
                "Bộ dữ liệu giá tải lên (dataset_id) không tồn tại hoặc đã hết hạn. Vui lòng tải lại file Excel/CSV giá lịch sử."
            )
        df_p_up = up_ds["df_prices"]
        missing_in_file = [s for s in clean_req_syms if s not in df_p_up.columns]
        if missing_in_file:
            raise ValueError(f"Các mã {', '.join(missing_in_file)} không có trong file giá đã tải lên.")
        df_sub = df_p_up[clean_req_syms].dropna(how="any").sort_index()
        moments = textbook_math.compute_moments_from_prices(df_sub, trading_days=252)
        df_prices_raw_bundle = df_sub
        df_volumes_bundle = up_ds.get("df_volumes")
        price_dates = up_ds.get("latest_price_dates") or {s: up_ds.get("to_date", "") for s in clean_req_syms}
        data_meta: dict[str, Any] = {
            "input_mode": "uploaded_prices",
            "source": f"File giá người dùng ({up_ds.get('filename', 'Uploaded')})",
            "filename": up_ds.get("filename"),
            "dataset_id": req.dataset_id,
            "fetched_at": up_ds.get("uploaded_at"),
            "range": "CUSTOM",
            "from_date": str(df_sub.index[0].date()),
            "to_date": str(df_sub.index[-1].date()),
            "aligned_price_sessions": int(len(df_sub)),
            "aligned_sessions": int(moments["sessions_count"]),
            "dropped_days_count": int(up_ds.get("dropped_days_count", 0)),
            "raw_session_counts": {s: int(len(df_p_up)) for s in clean_req_syms},
            "price_basis": "uploaded_price",
            "latest_price_dates": price_dates,
            "formula_version": "user-uploaded-prices",
        }
        price_source_kind = "uploaded_price"

    elif mode_canon == "manual_matrix":
        if not req.expected_returns or not req.std_devs or not req.corr_matrix:
            raise ValueError("Chế độ ma trận tham số cần đầy đủ E(R), độ lệch chuẩn σ và ma trận tương quan.")
        moments = textbook_math.build_moments_from_manual(
            symbols=clean_req_syms,
            expected_returns=req.expected_returns,
            std_devs=req.std_devs,
            corr_matrix=req.corr_matrix,
            latest_prices=req.latest_prices,
        )
        # Never attach any uploaded historical series into manual_matrix!
        lp_map = moments["latest_prices"]
        has_all_prices = all(
            lp_map.get(s) is not None and float(lp_map[s]) > 0
            for s in clean_req_syms
        )
        any_price = any(lp_map.get(s) is not None and float(lp_map[s]) > 0 for s in clean_req_syms)
        price_source_kind = "user_assumed" if (has_all_prices or any_price) else "missing"
        data_meta = {
            "input_mode": "manual_matrix",
            "source": "Ma trận Tham số Thủ công (Không có chuỗi giá lịch sử)",
            "filename": None,
            "dataset_id": None,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "range": "PARAMETRIC",
            "from_date": None,
            "to_date": None,
            "aligned_price_sessions": None,
            "aligned_sessions": None,
            "dropped_days_count": 0,
            "raw_session_counts": None,
            "price_basis": "user_matrix",
            "latest_price_dates": None,
            "formula_version": "manual-matrix",
        }

    else:
        live = hayinsights_client.fetch_multi_equity_dataset(
            symbols=clean_req_syms,
            range_str=req.hayinsights_range,
            use_adjusted=req.use_adjusted_close,
        )
        moments = textbook_math.compute_moments_from_prices(live["df_prices"], trading_days=252)
        moments["latest_prices"] = live["latest_raw_prices"]
        moments["volumes_df"] = live.get("df_volumes")
        df_prices_raw_bundle = live["df_prices"]
        df_volumes_bundle = live.get("df_volumes")
        data_meta = {
            "input_mode": "live_market",
            "source": "HayInsights Live API (Finhay / VNSC)",
            "filename": None,
            "dataset_id": None,
            "fetched_at": live.get("fetched_at"),
            "range": live["range"],
            "from_date": live["from_date"],
            "to_date": live["to_date"],
            "aligned_price_sessions": live.get("aligned_price_sessions"),
            "aligned_sessions": live.get("aligned_sessions"),
            "dropped_days_count": live.get("dropped_days_count", 0),
            "raw_session_counts": live.get("raw_session_counts"),
            "price_basis": live.get("price_basis"),
            "latest_price_dates": live.get("latest_price_dates"),
            "formula_version": live["formula_version"],
        }
        price_source_kind = "raw_close"

    symbols = moments["symbols"]
    n = len(symbols)
    mu = moments["mu"]
    cagr = moments.get("cagr")
    cov = moments["cov"]
    std = moments["std"]
    corr = moments["corr"]
    latest_prices = moments["latest_prices"]
    df_daily_rets = moments.get("daily_returns_df")

    if req.allow_short:
        sol = textbook_math.solve_merton_closed_form(mu, cov, req.rf, num_frontier=50)
        if sol.get("merton_status") == "singular_covariance":
            raise textbook_math.InfeasibleConstraintsError(
                "singular_covariance",
                "Ma trận hiệp phương sai suy biến (không khả nghịch), không thể giải nghiệm giải tích bán khống Merton.",
                "Hãy tắt chế độ bán khống (dùng QP Long-Only) hoặc loại bỏ mã có chuỗi lợi suất phụ thuộc tuyến tính.",
            )
        eff_w_min, eff_w_max = -1.0, 2.0
        bounds_note = None
        merton_ref = sol
    else:
        sol = textbook_math.solve_long_only_qp(
            mu,
            cov,
            req.rf,
            allow_short=False,
            w_min=req.w_min,
            w_max=req.w_max,
            num_frontier=50,
        )
        eff_w_min = sol["effective_w_min"]
        eff_w_max = sol["effective_w_max"]
        bounds_note = sol.get("bounds_adjusted_note")  # Always None
        merton_ref = sol.get("merton_reference", {})

    w_eq = np.ones(n) / n
    eq_stats = textbook_math._portfolio_stats(w_eq, mu, cov, req.rf)

    comp = textbook_math.compute_complete_portfolio(
        tangency_stats=sol["tangency_stats"],
        w_tangency=sol["w_tangency"],
        rf=req.rf,
        risk_aversion_gamma=gamma_val,
        allow_leverage=req.allow_short,
        cash_mode=req.cash_mode,
        mandated_cash_weight=req.mandated_cash_pct,
        tangency_status=sol.get("tangency_status", "optimal"),
    )

    execution = execution_engine.compute_execution_plan(
        symbols=symbols,
        w_risky=sol["w_tangency"].tolist(),
        y_risky=comp["y_star_risky_weight"],
        nav_vnd=req.nav_vnd,
        latest_prices=latest_prices,
        price_dates=data_meta.get("latest_price_dates"),
        price_source_kind=price_source_kind,
        w_min=float(eff_w_min),
        w_max=float(eff_w_max),
        lot_size=req.lot_size,
        buy_fee_rate=req.buy_fee_rate,
        allow_short=req.allow_short,
    )

    # Benchmark time horizon lookup: strictly respecting source mode isolation
    bm_rng = (req.benchmark_range or req.hayinsights_range or "1y").strip().lower()
    opt_rng = (req.hayinsights_range or "1y").strip().lower()
    df_bm_rets = df_daily_rets

    if mode_canon == "live_market" and bm_rng != opt_rng:
        try:
            live_bm = hayinsights_client.fetch_multi_equity_dataset(
                symbols=symbols,
                range_str=bm_rng,
                use_adjusted=req.use_adjusted_close,
            )
            df_bm_rets = live_bm["df_prices"].pct_change().dropna(how="any")
        except Exception:
            df_bm_rets = df_daily_rets
    elif mode_canon == "manual_matrix":
        df_bm_rets = None

    bm_comp = benchmark_engine.compute_benchmark_comparison(
        df_asset_returns=df_bm_rets,
        w_tangency=sol["w_tangency"],
        tangency_stats=sol["tangency_stats"],
        rf=req.rf,
        benchmark_symbol=req.benchmark_symbol,
        range_str=bm_rng,
        optimization_range=opt_rng if mode_canon == "live_market" else None,
    )

    stress_test = benchmark_engine.compute_stress_testing_and_var(
        df_asset_returns=df_daily_rets,
        w_tangency=sol["w_tangency"],
        tangency_stats=sol["tangency_stats"],
        complete_stats=comp,
        beta=bm_comp.get("beta"),
        nav_vnd=req.nav_vnd,
        rf=req.rf,
        execution_plan=execution,
        mu=mu,
        cov=cov,
    )

    mc_res = textbook_math.simulate_monte_carlo(
        mu=mu,
        cov=cov,
        rf=req.rf,
        n_portfolios=min(max(req.n_monte_carlo, 500), 6000),
        allow_short=req.allow_short,
        w_min=float(eff_w_min),
        w_max=float(eff_w_max),
        symbols=symbols,
        anchor_weights=[sol["w_gmv"], sol["w_tangency"]],
    )

    # Unconstrained Merton comparison block (strictly flagged as theoretical reference)
    merton_status = merton_ref.get("merton_status", "singular_covariance")
    inv_cov_raw = merton_ref.get("inv_cov")
    inv_cov_list = inv_cov_raw.tolist() if inv_cov_raw is not None else None
    merton_scalars = merton_ref.get("merton_scalars")

    if merton_status == "available" and merton_ref.get("w_tangency") is not None:
        m_w_tan = np.asarray(merton_ref["w_tangency"], dtype=float)
        m_w_gmv = np.asarray(merton_ref["w_gmv"], dtype=float)
        violates_active = bool(
            np.any(m_w_tan < eff_w_min - 1e-4)
            or np.any(m_w_tan > eff_w_max + 1e-4)
            or np.any(m_w_gmv < eff_w_min - 1e-4)
            or np.any(m_w_gmv > eff_w_max + 1e-4)
        )
        merton_unconstrained = {
            "merton_status": "available",
            "is_applied_in_active_portfolio": bool(req.allow_short),
            "violates_active_bounds": violates_active,
            "w_gmv": m_w_gmv.tolist(),
            "gmv_stats": merton_ref.get("gmv_stats"),
            "w_tangency": m_w_tan.tolist(),
            "tangency_stats": merton_ref.get("tangency_stats"),
            "message": None,
        }
    else:
        merton_unconstrained = {
            "merton_status": "singular_covariance",
            "is_applied_in_active_portfolio": False,
            "violates_active_bounds": False,
            "w_gmv": None,
            "gmv_stats": None,
            "w_tangency": None,
            "tangency_stats": None,
            "message": merton_ref.get("message"),
        }

    individual_assets = [
        {
            "symbol": symbols[i],
            "expected_return": float(mu[i]),
            "cagr": float(cagr[i]) if (cagr is not None and i < len(cagr)) else None,
            "volatility": float(std[i]),
            "variance": float(cov[i, i]),
            "sharpe_ratio": float((mu[i] - req.rf) / std[i]) if std[i] > 1e-8 else 0.0,
            "latest_price": latest_prices.get(symbols[i]),
            "latest_price_date": (data_meta.get("latest_price_dates") or {}).get(symbols[i]),
        }
        for i in range(n)
    ]

    run_id = uuid.uuid4().hex[:12]
    computed_at = datetime.now().isoformat(timespec="seconds")

    analysis_out = {
        "status": "success",
        "run_id": run_id,
        "computed_at": computed_at,
        "lang": req.lang,
        "risk_report_basis": req.risk_report_basis,
        "input_mode": req.input_mode,
        "input_mode_canonical": mode_canon,
        "allow_short": req.allow_short,
        "w_min": float(eff_w_min),
        "w_max": float(eff_w_max),
        "bounds_adjusted_note": bounds_note,
        "is_singleton": bool(sol.get("is_singleton", False)),
        "is_covariance_invertible": bool(sol.get("is_covariance_invertible", merton_status == "available")),
        "merton_status": merton_status,
        "tangency_status": sol.get("tangency_status", "optimal"),
        "cash_mode": comp["cash_mode"],
        "cash_mode_canonical": comp["cash_mode_canonical"],
        "mandated_cash_pct": float(req.mandated_cash_pct),
        "benchmark_symbol": bm_comp["benchmark_symbol"],
        "benchmark_range": bm_comp.get("benchmark_range", bm_rng.upper()),
        "trading_days": 252,
        "sessions_count": moments.get("sessions_count"),
        "rf": req.rf,
        "risk_aversion_gamma": gamma_val,
        "risk_aversion_A": gamma_val,
        "nav_vnd": req.nav_vnd,
        "lot_size": req.lot_size,
        "buy_fee_rate": req.buy_fee_rate,
        "symbols": symbols,
        "mu": mu.tolist(),
        "cagr": cagr.tolist() if cagr is not None else None,
        "std": std.tolist(),
        "cov": cov.tolist(),
        "corr": corr.tolist(),
        "inv_cov": inv_cov_list,
        "latest_prices": latest_prices,
        "merton_scalars": merton_scalars,
        "merton_unconstrained": merton_unconstrained,
        "individual_assets": individual_assets,
        "gmv": {
            "weights": sol["w_gmv"].tolist(),
            **sol["gmv_stats"],
        },
        "tangency": {
            "weights": sol["w_tangency"].tolist(),
            **sol["tangency_stats"],
        },
        "equal_weight": {
            "weights": w_eq.tolist(),
            **eq_stats,
        },
        "complete_portfolio": comp,
        "execution": execution,
        "benchmark_comparison": bm_comp,
        "stress_testing": stress_test,
        "frontier": sol["frontier"],
        "monte_carlo": mc_res["points"],
        "monte_carlo_meta": {
            "is_singleton": mc_res["is_singleton"],
            "seed": mc_res["seed"],
            "count": mc_res["count"],
            "w_min": mc_res["w_min"],
            "w_max": mc_res["w_max"],
        },
        "data_meta": data_meta,
    }

    _save_snapshot(
        run_id,
        analysis_out,
        {
            "df_prices": df_prices_raw_bundle,
            "df_volumes": df_volumes_bundle,
            "daily_returns_df": df_daily_rets,
            "latest_prices": latest_prices,
            "data_meta": data_meta,
            "symbols": symbols,
        },
    )
    return analysis_out


@app.get("/", response_class=HTMLResponse)
def index_page():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Đang khởi tạo giao diện Textbook MVO...</h1>")
    return HTMLResponse(
        content=html_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "portfolio-optimization-by-khim", "version": "2.5.0"}


@app.get("/api/presets")
def api_get_presets():
    key = hayinsights_client.load_api_key()
    return {
        "stocks": hayinsights_client.VN_TICKER_DIRECTORY[:10],
        "ticker_directory": hayinsights_client.VN_TICKER_DIRECTORY,
        "quiz_questions": risk_profiler.QUIZ_QUESTIONS,
        "trading_days_convention": 252,
        "hayinsights_configured": bool(key),
        "hayinsights_masked_key": f"{key[:8]}...{key[-4:]}" if len(key) > 12 else None,
    }


@app.get("/api/tickers")
def api_search_tickers(q: str = "", limit: int = 30):
    return {
        "query": q,
        "results": hayinsights_client.search_tickers(query=q, limit=limit),
    }


@app.get("/api/hayinsights/quote/{symbol}")
def api_quote_ticker(symbol: str):
    try:
        return hayinsights_client.validate_and_quote_ticker(symbol)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/quiz")
def api_evaluate_quiz(sub: QuizSubmission):
    try:
        return risk_profiler.evaluate_risk_profile(sub.scores)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/optimize")
def api_optimize(req: OptimizeRequest):
    try:
        return _build_full_analysis(req)
    except textbook_math.InfeasibleConstraintsError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": exc.code,
                "message": exc.message,
                "suggestion": exc.suggestion,
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/benchmark-attribution")
def api_benchmark_attribution(req: BenchmarkAttributionRequest):
    """
    Fast Benchmark Attribution endpoint strictly isolated by data source mode:
    - live_market: queries HayInsights for benchmark horizon.
    - uploaded_prices: slices uploaded dataset by explicit dataset_id (never touches live API).
    - manual_matrix: returns status='unavailable' without touching HayInsights or uploaded cache.
    """
    try:
        bm_sym = (req.benchmark_symbol or "VNINDEX").strip().upper()
        bm_rng = (req.benchmark_range or "1y").strip().lower()
        mode_canon = _normalize_input_mode(req.input_mode)
        clean_syms = [s.strip().upper() for s in req.symbols if s.strip()]
        w_tan = np.asarray(req.w_tangency, dtype=float)
        tan_stats = {
            "expected_return": float(req.tangency_return),
            "volatility": float(req.tangency_volatility),
            "sharpe_ratio": float(req.tangency_sharpe),
        }

        if mode_canon == "manual_matrix":
            return benchmark_engine.compute_benchmark_comparison(
                df_asset_returns=None,
                w_tangency=w_tan,
                tangency_stats=tan_stats,
                rf=req.rf,
                benchmark_symbol=bm_sym,
                range_str=bm_rng,
            )

        if mode_canon == "uploaded_prices":
            up_ds = data_loader.get_uploaded_dataset(req.dataset_id)
            if not up_ds or up_ds.get("df_prices") is None:
                raise ValueError("Dataset tải lên không còn tồn tại; vui lòng tải lại file giá.")
            df_p = up_ds["df_prices"][clean_syms].dropna(how="any").sort_index()
            df_rets = df_p.pct_change().dropna(how="any")
        else:
            live_bm = hayinsights_client.fetch_multi_equity_dataset(
                symbols=clean_syms,
                range_str=bm_rng,
                use_adjusted=req.use_adjusted_close,
            )
            df_rets = live_bm["df_prices"].pct_change().dropna(how="any")

        res = benchmark_engine.compute_benchmark_comparison(
            df_asset_returns=df_rets,
            w_tangency=w_tan,
            tangency_stats=tan_stats,
            rf=req.rf,
            benchmark_symbol=bm_sym,
            range_str=bm_rng,
            optimization_range=req.optimization_range,
        )
        return res
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload-excel")
async def api_upload_excel(file: UploadFile = File(...)):
    try:
        content = await file.read()
        moments = data_loader.parse_uploaded_file(content, file.filename or "upload.xlsx")
        return {
            "status": "success",
            "source_type": moments.get("source_type", "uploaded"),
            "dataset_id": moments.get("dataset_id"),
            "filename": moments.get("filename"),
            "uploaded_at": moments.get("uploaded_at"),
            "from_date": moments.get("from_date"),
            "to_date": moments.get("to_date"),
            "dropped_days_count": moments.get("dropped_days_count"),
            "aligned_price_sessions": moments.get("aligned_price_sessions"),
            "symbols": moments["symbols"],
            "expected_returns": moments["mu"].tolist(),
            "std_devs": moments["std"].tolist(),
            "corr_matrix": moments["corr"].tolist(),
            "cov_matrix": moments["cov"].tolist(),
            "latest_prices": moments["latest_prices"],
            "latest_price_dates": moments.get("latest_price_dates"),
            "sessions_count": moments["sessions_count"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/template/{kind}")
def api_download_template(kind: str = "parameters"):
    mode = "prices" if kind.lower() == "prices" else "parameters"
    xlsx_bytes = template_generator.generate_input_template_xlsx(mode=mode)
    fname = f"MVO_Template_{mode.capitalize()}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/export-prices")
def api_export_prices(req: OptimizeRequest):
    """
    Export exact historical price series, volumes & daily returns for the active snapshot (run_id)
    or explicit dataset. Never falls back across modes or uses HayInsights in manual_matrix mode.
    """
    try:
        if req.run_id:
            analysis, df_bundle = _get_snapshot_or_404(req.run_id)
            mode_canon = analysis["input_mode_canonical"]
            if mode_canon == "manual_matrix" or df_bundle.get("df_prices") is None:
                raise HTTPException(
                    status_code=400,
                    detail="Chế độ ma trận tham số không có chuỗi giá lịch sử để xuất file Price Data.",
                )
            clean_syms = df_bundle["symbols"]
            df_prices = df_bundle["df_prices"]
            df_volumes = df_bundle.get("df_volumes")
            daily_rets = df_bundle.get("daily_returns_df")
            latest_prices = df_bundle.get("latest_prices", {})
            meta = df_bundle.get("data_meta", {})
            win_tag = str(meta.get("range", "Custom")).upper()
        else:
            mode_canon = _normalize_input_mode(req.input_mode)
            clean_syms = [s.strip().upper() for s in req.symbols if s.strip()]
            if mode_canon == "manual_matrix":
                raise HTTPException(
                    status_code=400,
                    detail="Chế độ ma trận tham số không có chuỗi giá lịch sử để xuất file Price Data.",
                )
            if mode_canon == "uploaded_prices":
                up_ds = data_loader.get_uploaded_dataset(req.dataset_id)
                if not up_ds or up_ds.get("df_prices") is None:
                    raise HTTPException(status_code=400, detail="Không tìm thấy dữ liệu giá tải lên để xuất.")
                df_prices = up_ds["df_prices"][clean_syms]
                df_volumes = up_ds.get("df_volumes")
                daily_rets = up_ds.get("daily_returns_df")
                latest_prices = up_ds.get("latest_prices", {})
                win_tag = "Uploaded"
                meta = {
                    "source": f"Uploaded Excel ({up_ds.get('filename', 'User File')})",
                    "range": "Custom",
                    "from_date": up_ds.get("from_date"),
                    "to_date": up_ds.get("to_date"),
                    "dropped_days_count": up_ds.get("dropped_days_count", 0),
                    "formula_version": "user-uploaded-prices",
                }
            else:
                win_str = req.hayinsights_range or "1y"
                live = hayinsights_client.fetch_multi_equity_dataset(
                    symbols=clean_syms,
                    range_str=win_str,
                    use_adjusted=req.use_adjusted_close,
                )
                moments = textbook_math.compute_moments_from_prices(live["df_prices"], trading_days=252)
                df_prices = live["df_prices"]
                df_volumes = live.get("df_volumes")
                daily_rets = moments.get("daily_returns_df")
                latest_prices = live["latest_raw_prices"]
                win_tag = win_str.upper()
                meta = {
                    "source": "HayInsights Live API (Finhay / VNSC)",
                    "range": live["range"],
                    "from_date": live["from_date"],
                    "to_date": live["to_date"],
                    "dropped_days_count": live.get("dropped_days_count", 0),
                    "formula_version": live["formula_version"],
                }

        xlsx_bytes = data_exporter.export_live_price_dataset_xlsx(
            symbols=clean_syms,
            df_prices=df_prices,
            df_volumes=df_volumes,
            daily_returns_df=daily_rets,
            latest_prices=latest_prices,
            data_meta=meta,
            lang=req.lang,
        )
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_Prices_{len(clean_syms)}Assets_{win_tag}_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-matrix")
def api_export_matrix(req: OptimizeRequest):
    """Export E(R), σ, Correlation P, Covariance Σ directly from committed snapshot (run_id) or solve fresh."""
    try:
        if req.run_id:
            analysis, _ = _get_snapshot_or_404(req.run_id)
        else:
            analysis = _build_full_analysis(req)
        symbols = analysis["symbols"]
        xlsx_bytes = data_exporter.export_live_parameter_matrix_xlsx(
            symbols=symbols,
            mu=analysis["mu"],
            std=analysis["std"],
            corr=analysis["corr"],
            cov=analysis["cov"],
            latest_prices=analysis.get("latest_prices"),
            rf=analysis["rf"],
            data_meta=analysis.get("data_meta"),
            lang=req.lang,
        )
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_Matrix_{len(symbols)}Assets_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-excel")
def api_export_excel(req: OptimizeRequest):
    """Export 8-sheet MVO report directly from committed snapshot (run_id) or solve fresh."""
    try:
        if req.run_id:
            analysis, _ = _get_snapshot_or_404(req.run_id)
        else:
            analysis = _build_full_analysis(req)
        xlsx_bytes = excel_exporter.export_mvo_institutional_workbook(
            analysis,
            lang=req.lang,
            risk_report_basis=req.risk_report_basis,
        )
        mode_tag = "ShortAllowed" if analysis.get("allow_short") else "LongOnly"
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_MVO_Institutional_Report_{mode_tag}_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
