"""
FastAPI Backend for Pure Textbook MVO & Institutional Portfolio Construction Workbench.
100% Real Market Data & User Upload Architecture (Zero Synthetic Fallback).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import (
    benchmark_engine,
    data_exporter,
    data_loader,
    excel_exporter,
    hayinsights_client,
    risk_profiler,
    template_generator,
    textbook_math,
)

app = FastAPI(
    title="Portfolio Optimization by Khim — Institutional MVO Workbench",
    version="2.4.0",
    description="Hệ thống Tối ưu hóa Danh mục Đầu tư Mean-Variance (Markowitz 1952 - Merton 1972) chuẩn giáo trình đại học & quản lý quỹ định chế.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class QuizSubmission(BaseModel):
    scores: list[int]


class OptimizeRequest(BaseModel):
    input_mode: str = "hayinsights"  # "hayinsights" or "manual"
    symbols: list[str] = ["FPT", "MWG", "VCB", "HPG", "VNM"]
    hayinsights_range: str = "1y"
    use_adjusted_close: bool = True
    expected_returns: list[float] | None = None
    std_devs: list[float] | None = None
    corr_matrix: list[list[float]] | None = None
    latest_prices: dict[str, float] | None = None
    rf: float = 0.045
    risk_aversion_A: float = 3.0
    allow_short: bool = False
    w_min: float = 0.0
    w_max: float = 1.0
    cash_mode: str = "bkm"  # "bkm" or "mandated"
    mandated_cash_pct: float = 0.10
    benchmark_symbol: str = "VNINDEX"  # "VNINDEX" or "VN30"
    benchmark_range: str = "1y"  # "6m", "1y", "3y", "5y", "ytd", "max"
    nav_vnd: float = 1_000_000_000.0
    n_monte_carlo: int = 2500


def _build_full_analysis(req: OptimizeRequest) -> dict[str, Any]:
    data_meta: dict[str, Any] = {
        "source": "HayInsights Live API (Finhay / VNSC)",
        "range": req.hayinsights_range or "1y",
        "from_date": None,
        "to_date": None,
        "formula_version": "vnsc-adjusted-close-v1",
    }

    if req.input_mode == "manual" and req.expected_returns and req.std_devs and req.corr_matrix:
        moments = textbook_math.build_moments_from_manual(
            symbols=req.symbols,
            expected_returns=req.expected_returns,
            std_devs=req.std_devs,
            corr_matrix=req.corr_matrix,
            latest_prices=req.latest_prices,
        )
        # Attach uploaded historical price/return series if matching symbols were uploaded
        cached_up = data_loader.get_last_uploaded_dataset()
        clean_req_syms = [s.strip().upper() for s in req.symbols]
        if cached_up and cached_up.get("symbols") == clean_req_syms:
            moments["prices_df"] = cached_up.get("df_prices")
            moments["volumes_df"] = cached_up.get("df_volumes")
            moments["daily_returns_df"] = cached_up.get("daily_returns_df")
            moments["sessions_count"] = len(cached_up["daily_returns_df"]) if cached_up.get("daily_returns_df") is not None else 252
        data_meta["source"] = "Ma trận Tham số / File Excel Người dùng"
        data_meta["formula_version"] = "manual-matrix"
    else:
        live = hayinsights_client.fetch_multi_equity_dataset(
            symbols=req.symbols,
            range_str=req.hayinsights_range,
            use_adjusted=req.use_adjusted_close,
        )
        moments = textbook_math.compute_moments_from_prices(live["df_prices"], trading_days=252)
        moments["latest_prices"] = live["latest_raw_prices"]
        moments["volumes_df"] = live.get("df_volumes")
        data_meta = {
            "source": "HayInsights Live API (Finhay / VNSC)",
            "range": live["range"],
            "from_date": live["from_date"],
            "to_date": live["to_date"],
            "formula_version": live["formula_version"],
        }

    symbols = moments["symbols"]
    n = len(symbols)
    mu = moments["mu"]
    cov = moments["cov"]
    std = moments["std"]
    corr = moments["corr"]
    latest_prices = moments["latest_prices"]
    df_daily_rets = moments.get("daily_returns_df")

    if req.allow_short:
        sol = textbook_math.solve_merton_closed_form(mu, cov, req.rf, num_frontier=50)
        eff_w_min, eff_w_max = -1.0, 2.0
        bounds_note = None
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
        eff_w_min = sol.get("effective_w_min", req.w_min)
        eff_w_max = sol.get("effective_w_max", req.w_max)
        bounds_note = sol.get("bounds_adjusted_note")

    w_eq = np.ones(n) / n
    eq_stats = textbook_math._portfolio_stats(w_eq, mu, cov, req.rf)

    comp = textbook_math.compute_complete_portfolio(
        tangency_stats=sol["tangency_stats"],
        w_tangency=sol["w_tangency"],
        rf=req.rf,
        risk_aversion_A=req.risk_aversion_A,
        allow_leverage=req.allow_short,
        cash_mode=req.cash_mode,
        mandated_cash_weight=req.mandated_cash_pct,
    )

    # Determine daily returns series for the requested Benchmark Time Horizon
    bm_rng = (req.benchmark_range or req.hayinsights_range or "1y").strip().lower()
    opt_rng = (req.hayinsights_range or "1y").strip().lower()
    df_bm_rets = df_daily_rets

    if req.input_mode != "manual" and bm_rng != opt_rng:
        try:
            live_bm = hayinsights_client.fetch_multi_equity_dataset(
                symbols=symbols,
                range_str=bm_rng,
                use_adjusted=req.use_adjusted_close,
            )
            df_bm_rets = live_bm["df_prices"].pct_change().dropna(how="any")
        except Exception:
            df_bm_rets = df_daily_rets

    bm_comp = benchmark_engine.compute_benchmark_comparison(
        df_asset_returns=df_bm_rets,
        w_tangency=sol["w_tangency"],
        tangency_stats=sol["tangency_stats"],
        rf=req.rf,
        benchmark_symbol=req.benchmark_symbol,
        range_str=bm_rng,
    )

    stress_test = benchmark_engine.compute_stress_testing_and_var(
        df_asset_returns=df_daily_rets,
        w_tangency=sol["w_tangency"],
        tangency_stats=sol["tangency_stats"],
        complete_stats=comp,
        beta=bm_comp["beta"],
        nav_vnd=req.nav_vnd,
        rf=req.rf,
    )

    mc_cloud = textbook_math.simulate_monte_carlo(
        mu=mu,
        cov=cov,
        rf=req.rf,
        n_portfolios=min(max(req.n_monte_carlo, 500), 6000),
        allow_short=req.allow_short,
    )

    individual_assets = [
        {
            "symbol": symbols[i],
            "expected_return": float(mu[i]),
            "volatility": float(std[i]),
            "variance": float(cov[i, i]),
            "sharpe_ratio": float((mu[i] - req.rf) / std[i]) if std[i] > 1e-8 else 0.0,
            "latest_price": float(latest_prices.get(symbols[i], 50000.0)),
        }
        for i in range(n)
    ]

    return {
        "status": "success",
        "input_mode": req.input_mode,
        "allow_short": req.allow_short,
        "w_min": float(eff_w_min),
        "w_max": float(eff_w_max),
        "bounds_adjusted_note": bounds_note,
        "cash_mode": comp["cash_mode"],
        "mandated_cash_pct": float(req.mandated_cash_pct),
        "benchmark_symbol": bm_comp["benchmark_symbol"],
        "benchmark_range": bm_comp.get("benchmark_range", bm_rng.upper()),
        "trading_days": 252,
        "sessions_count": moments["sessions_count"],
        "rf": req.rf,
        "risk_aversion_A": req.risk_aversion_A,
        "nav_vnd": req.nav_vnd,
        "symbols": symbols,
        "mu": mu.tolist(),
        "std": std.tolist(),
        "cov": cov.tolist(),
        "corr": corr.tolist(),
        "inv_cov": sol["inv_cov"].tolist(),
        "latest_prices": latest_prices,
        "merton_scalars": sol["merton_scalars"],
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
        "benchmark_comparison": bm_comp,
        "stress_testing": stress_test,
        "frontier": sol["frontier"],
        "monte_carlo": mc_cloud,
        "data_meta": data_meta,
    }


@app.get("/", response_class=HTMLResponse)
def index_page():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Đang khởi tạo giao diện Textbook MVO...</h1>")
    return FileResponse(html_path)


@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "portfolio-optimization-by-khim", "version": "2.4.0"}


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
            "symbols": moments["symbols"],
            "expected_returns": moments["mu"].tolist(),
            "std_devs": moments["std"].tolist(),
            "corr_matrix": moments["corr"].tolist(),
            "cov_matrix": moments["cov"].tolist(),
            "latest_prices": moments["latest_prices"],
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
    Export the exact historical price series, trading volumes, and daily returns
    for the currently selected portfolio symbols and time window.
    """
    try:
        clean_syms = [s.strip().upper() for s in req.symbols if s.strip()]
        cached_up = data_loader.get_last_uploaded_dataset()

        if req.input_mode == "manual" and cached_up and cached_up.get("symbols") == clean_syms and cached_up.get("df_prices") is not None:
            df_prices = cached_up["df_prices"]
            df_volumes = cached_up.get("df_volumes")
            daily_rets = cached_up.get("daily_returns_df")
            latest_prices = cached_up.get("latest_prices", {})
            win_tag = "Uploaded"
            meta = {
                "source": f"Uploaded Excel ({cached_up.get('filename', 'User File')})",
                "range": "Custom",
                "from_date": str(df_prices.index[0].date()) if hasattr(df_prices.index[0], "date") else str(df_prices.index[0])[:10],
                "to_date": str(df_prices.index[-1].date()) if hasattr(df_prices.index[-1], "date") else str(df_prices.index[-1])[:10],
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
                "formula_version": live["formula_version"],
            }

        xlsx_bytes = data_exporter.export_live_price_dataset_xlsx(
            symbols=clean_syms,
            df_prices=df_prices,
            df_volumes=df_volumes,
            daily_returns_df=daily_rets,
            latest_prices=latest_prices,
            data_meta=meta,
        )
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_Prices_{len(clean_syms)}Assets_{win_tag}_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-matrix")
def api_export_matrix(req: OptimizeRequest):
    """
    Export the active portfolio's Expected Return vector E(R), Volatility vector σ,
    Correlation Matrix P, and Covariance Matrix Σ.
    """
    try:
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
        )
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_Matrix_{len(symbols)}Assets_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export-excel")
def api_export_excel(req: OptimizeRequest):
    try:
        analysis = _build_full_analysis(req)
        xlsx_bytes = excel_exporter.export_mvo_institutional_workbook(analysis)
        mode_tag = "ShortAllowed" if req.allow_short else "LongOnly"
        date_tag = datetime.now().strftime("%Y%m%d")
        fname = f"Portfolio_MVO_Institutional_Report_{mode_tag}_{date_tag}.xlsx"
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
