"""
Institutional Benchmark Comparison (VN-Index / VN30) & Tail-Risk Stress Testing Engine.
Provides:
1. Real-time / Historical VN-Index & VN30 daily index series via VNDirect DChart API (with TTL cache & deterministic fallback).
2. Relative Performance & Active Risk Metrics:
   - Portfolio Beta (β), Jensen's Alpha (α), Tracking Error (TE), Information Ratio (IR), Active Return, R².
3. Value at Risk (VaR), Conditional VaR (CVaR / Expected Shortfall), Maximum Drawdown (MDD).
4. Historical Vietnam Stock Market Crisis Stress Testing:
   - Covid-19 Crash (Mar 2020: -33.5%)
   - Rate Hike & Corporate Bond Crisis (2022: -34.1%)
   - FX Pressure & SBV T-Bill Issuance (Apr 2024: -8.5%)
   - Standard Risk Committee Shock (-15.0%)
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from typing import Any

import numpy as np
import pandas as pd

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

TRADING_DAYS = 252
_BENCHMARK_CACHE: dict[tuple[str, str], tuple[float, pd.Series]] = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

RANGE_DAYS_MAP = {
    "6m": 190,
    "1y": 380,
    "2y": 750,
    "3y": 1120,
    "5y": 1850,
    "ytd": 380,
    "max": 3650,
}


def _generate_fallback_benchmark_series(symbol: str = "VNINDEX", n_days: int = 260) -> pd.Series:
    """
    Deterministic calibrated benchmark series if external index API is unreachable.
    Calibrated to historical Vietnam market characteristics.
    """
    sym = symbol.upper()
    seed = 2026 if sym == "VNINDEX" else 2030
    rng = np.random.default_rng(seed)

    ann_ret = 0.115 if sym == "VNINDEX" else 0.128
    ann_vol = 0.178 if sym == "VNINDEX" else 0.188
    base_level = 1250.0 if sym == "VNINDEX" else 1320.0

    daily_mu = ann_ret / TRADING_DAYS
    daily_sigma = ann_vol / math.sqrt(TRADING_DAYS)

    shocks = rng.normal(daily_mu, daily_sigma, size=n_days)
    levels = base_level * np.cumprod(1.0 + shocks)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)
    return pd.Series(levels, index=dates, name=sym)


def _slice_series_by_horizon(s: pd.Series | pd.DataFrame, rng_key: str):
    """Slice a DatetimeIndex Series or DataFrame according to horizon ('6m', '1y', '2y', '3y', '5y', 'ytd', 'max')."""
    if len(s) < 5:
        return s
    last_dt = s.index[-1]
    rk = (rng_key or "1y").strip().lower()
    if rk == "ytd":
        cutoff = pd.Timestamp(year=last_dt.year, month=1, day=1)
    elif rk == "6m":
        cutoff = last_dt - pd.Timedelta(days=183)
    elif rk == "1y":
        cutoff = last_dt - pd.Timedelta(days=366)
    elif rk == "2y":
        cutoff = last_dt - pd.Timedelta(days=731)
    elif rk == "3y":
        cutoff = last_dt - pd.Timedelta(days=1096)
    elif rk == "5y":
        cutoff = last_dt - pd.Timedelta(days=1826)
    else:
        return s
    sliced = s[s.index >= cutoff]
    return sliced if len(sliced) >= 5 else s


def fetch_benchmark_series(symbol: str = "VNINDEX", range_str: str = "1y") -> pd.Series:
    """
    Fetch daily closing levels for VNINDEX or VN30 from VNDirect DChart API.
    Supports horizons: 6m, 1y, 2y, 3y, 5y, ytd, max.
    Automatically caches in memory and falls back cleanly if offline.
    """
    sym = (symbol or "VNINDEX").strip().upper()
    if sym not in ("VNINDEX", "VN30"):
        sym = "VNINDEX"
    rng_key = (range_str or "1y").strip().lower()
    cache_key = (sym, rng_key)

    now = time.time()
    if cache_key in _BENCHMARK_CACHE:
        ts, cached_series = _BENCHMARK_CACHE[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return cached_series.copy()

    lookback_days = RANGE_DAYS_MAP.get(rng_key, 380)
    to_ts = int(now)
    from_ts = to_ts - (lookback_days * 86400)
    url = (
        f"https://dchart-api.vndirect.com.vn/dchart/history"
        f"?resolution=D&symbol={sym}&from={from_ts}&to={to_ts}"
    )

    try:
        if HAS_CFFI:
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=6)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            payload = resp.json()
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                payload = json.loads(r.read().decode("utf-8"))

        timestamps = payload.get("t", [])
        closes = payload.get("c", [])
        if not timestamps or len(timestamps) < 10:
            raise ValueError("Insufficient benchmark points")

        dates = pd.to_datetime(timestamps, unit="s").normalize()
        s = pd.Series(closes, index=dates, name=sym, dtype=float)
        s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
        s = _slice_series_by_horizon(s, rng_key)
        _BENCHMARK_CACHE[cache_key] = (now, s)
        return s.copy()
    except Exception:
        n_sessions = max(60, int(lookback_days * 252 / 365))
        s_fb = _generate_fallback_benchmark_series(sym, n_days=n_sessions)
        s_fb = _slice_series_by_horizon(s_fb, rng_key)
        _BENCHMARK_CACHE[cache_key] = (now, s_fb)
        return s_fb.copy()


def compute_benchmark_comparison(
    df_asset_returns: pd.DataFrame | None,
    w_tangency: np.ndarray,
    tangency_stats: dict[str, float],
    rf: float,
    benchmark_symbol: str = "VNINDEX",
    range_str: str = "1y",
) -> dict[str, Any]:
    """
    Compute institutional relative performance metrics of Tangency Portfolio vs Benchmark (VN-Index / VN30):
    - Benchmark Annualized Return E(R_m), Volatility σ_m, Sharpe Ratio
    - Portfolio Beta (β), Jensen's Alpha (α)
    - Tracking Error (TE), Active Return, Information Ratio (IR), Correlation, R²
    - Cumulative Wealth Index (Base 100) for Portfolio vs Benchmark across selected Time Horizon
    """
    bm_sym = (benchmark_symbol or "VNINDEX").strip().upper()
    if bm_sym not in ("VNINDEX", "VN30"):
        bm_sym = "VNINDEX"
    rng_key = (range_str or "1y").strip().lower()

    port_ret = float(tangency_stats["expected_return"])
    port_vol = float(tangency_stats["volatility"])
    port_sr = float(tangency_stats["sharpe_ratio"])

    if df_asset_returns is not None and len(df_asset_returns) >= 10:
        s_bm = fetch_benchmark_series(bm_sym, range_str=rng_key)
        r_bm = s_bm.pct_change().dropna()

        # Normalize indices to date-only for exact alignment
        df_port_ret = df_asset_returns.copy()
        df_port_ret.index = pd.to_datetime(df_port_ret.index).normalize()
        df_port_ret = _slice_series_by_horizon(df_port_ret, rng_key)
        r_bm.index = pd.to_datetime(r_bm.index).normalize()

        common_idx = df_port_ret.index.intersection(r_bm.index)
        if len(common_idx) >= 10:
            p_daily = (df_port_ret.loc[common_idx] @ w_tangency).to_numpy(dtype=float, copy=True)
            m_daily = r_bm.loc[common_idx].to_numpy(dtype=float, copy=True)
            dates_str = [d.strftime("%Y-%m-%d") for d in common_idx]
        else:
            p_daily = (df_port_ret @ w_tangency).to_numpy(dtype=float, copy=True)
            m_len = min(len(p_daily), len(r_bm))
            p_daily = p_daily[-m_len:]
            m_daily = r_bm.to_numpy(dtype=float, copy=True)[-m_len:]
            dates_str = [d.strftime("%Y-%m-%d") for d in df_port_ret.index[-m_len:]]

        if len(p_daily) >= 10:
            port_ret = float(np.mean(p_daily) * TRADING_DAYS)
            port_vol = float(np.std(p_daily, ddof=1) * math.sqrt(TRADING_DAYS))
            port_sr = (port_ret - rf) / port_vol if port_vol > 1e-8 else 0.0

        bm_ret = float(np.mean(m_daily) * TRADING_DAYS)
        bm_vol = float(np.std(m_daily, ddof=1) * math.sqrt(TRADING_DAYS))
        bm_sr = (bm_ret - rf) / bm_vol if bm_vol > 1e-8 else 0.0

        var_m = float(np.var(m_daily, ddof=1) * TRADING_DAYS)
        cov_pm = float(np.cov(p_daily, m_daily, ddof=1)[0, 1] * TRADING_DAYS) if len(p_daily) > 2 else 0.0
        beta = cov_pm / var_m if var_m > 1e-10 else 1.0

        corr_val = float(np.corrcoef(p_daily, m_daily)[0, 1]) if (np.std(p_daily) > 1e-10 and np.std(m_daily) > 1e-10) else 0.0
        r_squared = corr_val**2

        active_daily = p_daily - m_daily
        tracking_error = float(np.std(active_daily, ddof=1) * math.sqrt(TRADING_DAYS))
        active_return = port_ret - bm_ret
        information_ratio = active_return / tracking_error if tracking_error > 1e-8 else 0.0
        jensen_alpha = port_ret - (rf + beta * (bm_ret - rf))

        cum_port = (100.0 * np.cumprod(1.0 + p_daily)).round(2).tolist()
        cum_bm = (100.0 * np.cumprod(1.0 + m_daily)).round(2).tolist()
    else:
        # Manual Matrix Mode: parametric benchmark comparison
        bm_ret = 0.115 if bm_sym == "VNINDEX" else 0.128
        bm_vol = 0.180 if bm_sym == "VNINDEX" else 0.190
        bm_sr = (bm_ret - rf) / bm_vol
        corr_val = 0.76
        r_squared = corr_val**2
        beta = corr_val * (port_vol / bm_vol) if bm_vol > 1e-8 else 1.0
        tracking_error = math.sqrt(max(port_vol**2 + bm_vol**2 - 2 * corr_val * port_vol * bm_vol, 1e-6))
        active_return = port_ret - bm_ret
        information_ratio = active_return / tracking_error if tracking_error > 1e-8 else 0.0
        jensen_alpha = port_ret - (rf + beta * (bm_ret - rf))
        dates_str = []
        cum_port = []
        cum_bm = []

    return {
        "benchmark_symbol": bm_sym,
        "benchmark_range": rng_key.upper(),
        "sessions_compared": len(dates_str),
        "benchmark_name": "VN-Index (HOSE Composite)" if bm_sym == "VNINDEX" else "VN30 Index (Large-Cap Bluechips)",
        "benchmark_return": float(bm_ret),
        "benchmark_volatility": float(bm_vol),
        "benchmark_sharpe": float(bm_sr),
        "portfolio_return": float(port_ret),
        "portfolio_volatility": float(port_vol),
        "portfolio_sharpe": float(port_sr),
        "active_return": float(active_return),
        "sharpe_spread": float(port_sr - bm_sr),
        "beta": float(beta),
        "jensen_alpha": float(jensen_alpha),
        "tracking_error": float(tracking_error),
        "information_ratio": float(information_ratio),
        "correlation": float(corr_val),
        "r_squared": float(r_squared),
        "cumulative_series": {
            "dates": dates_str,
            "portfolio_base100": cum_port,
            "benchmark_base100": cum_bm,
        },
    }


def compute_stress_testing_and_var(
    df_asset_returns: pd.DataFrame | None,
    w_tangency: np.ndarray,
    tangency_stats: dict[str, float],
    complete_stats: dict[str, Any],
    beta: float,
    nav_vnd: float,
    rf: float,
) -> dict[str, Any]:
    """
    Compute Tail-Risk Metrics (VaR 95%/99%, CVaR/Expected Shortfall, Maximum Drawdown)
    and simulate 4 Historical / Institutional Stress Scenarios on Complete Portfolio NAV.
    """
    y_risky = float(complete_stats.get("y_star_risky_weight", 1.0))
    w_cash = float(complete_stats.get("w_rf_weight", 1.0 - y_risky))
    comp_ret_ann = float(complete_stats.get("expected_return", tangency_stats["expected_return"]))
    comp_vol_ann = float(complete_stats.get("volatility", tangency_stats["volatility"]))

    daily_mu = comp_ret_ann / TRADING_DAYS
    daily_sigma = comp_vol_ann / math.sqrt(TRADING_DAYS)

    if df_asset_returns is not None and len(df_asset_returns) >= 20:
        r_risky_daily = (df_asset_returns @ w_tangency).to_numpy(dtype=float, copy=True)
        r_comp_daily = y_risky * r_risky_daily + w_cash * (rf / TRADING_DAYS)

        # Historical VaR (positive number representing loss magnitude)
        var_95_1d = float(max(0.0, -np.percentile(r_comp_daily, 5)))
        var_99_1d = float(max(0.0, -np.percentile(r_comp_daily, 1)))

        tail_95 = r_comp_daily[r_comp_daily <= -var_95_1d]
        cvar_95_1d = float(max(var_95_1d, -np.mean(tail_95))) if len(tail_95) > 0 else var_95_1d * 1.25

        tail_99 = r_comp_daily[r_comp_daily <= -var_99_1d]
        cvar_99_1d = float(max(var_99_1d, -np.mean(tail_99))) if len(tail_99) > 0 else var_99_1d * 1.15

        # Maximum Drawdown from historical cumulative wealth
        wealth_comp = np.cumprod(1.0 + r_comp_daily)
        peak_comp = np.maximum.accumulate(wealth_comp)
        dd_comp = (wealth_comp - peak_comp) / peak_comp
        max_drawdown = float(abs(np.min(dd_comp)))

        wealth_risky = np.cumprod(1.0 + r_risky_daily)
        peak_risky = np.maximum.accumulate(wealth_risky)
        dd_risky = (wealth_risky - peak_risky) / peak_risky
        max_drawdown_risky = float(abs(np.min(dd_risky)))
        method_used = "Historical Simulation"
    else:
        # Parametric Gaussian VaR & CVaR
        var_95_1d = max(0.0, -(daily_mu - 1.64485 * daily_sigma))
        var_99_1d = max(0.0, -(daily_mu - 2.32635 * daily_sigma))
        cvar_95_1d = max(0.0, -daily_mu + 2.06271 * daily_sigma)
        cvar_99_1d = max(0.0, -daily_mu + 2.66521 * daily_sigma)
        max_drawdown = min(0.85, comp_vol_ann * 1.35)
        max_drawdown_risky = min(0.90, float(tangency_stats["volatility"]) * 1.35)
        method_used = "Parametric Normal"

    # Scale to 1-Month (21 trading days)
    sqrt_21 = math.sqrt(21.0)
    var_95_21d = min(0.95, var_95_1d * sqrt_21)
    var_99_21d = min(0.98, var_99_1d * sqrt_21)
    cvar_95_21d = min(0.98, cvar_95_1d * sqrt_21)

    # Historical Crisis Scenarios of Vietnam Stock Market
    raw_scenarios = [
        {
            "id": "covid_2020",
            "name": "Cú sốc Đại dịch Covid-19 (03/2020)",
            "period": "Q1/2020",
            "market_shock_pct": -0.335,
            "description": "VN-Index giảm từ 990 về 659 điểm do giãn cách xã hội toàn cầu.",
        },
        {
            "id": "bond_crisis_2022",
            "name": "Khủng hoảng Trái phiếu & Lãi suất (2022)",
            "period": "04/2022 - 11/2022",
            "market_shock_pct": -0.341,
            "description": "Lãi suất tăng 200bps, áp lực giải chấp chéo và khủng hoảng TPDN.",
        },
        {
            "id": "fx_sbv_2024",
            "name": "Áp lực Tỷ giá & Hút Tín phiếu (04/2024)",
            "period": "04/2024",
            "market_shock_pct": -0.085,
            "description": "USD/VND căng thẳng, NHNN phát hành tín phiếu hút thanh khoản.",
        },
        {
            "id": "stress_15pct",
            "name": "Kịch bản Kiểm định Ủy ban Rủi ro (-15%)",
            "period": "Standard Shock",
            "market_shock_pct": -0.150,
            "description": "Bài kiểm tra sức chịu đựng tiêu chuẩn khi thị trường điều chỉnh 15%.",
        },
    ]

    effective_beta = max(0.2, min(2.5, float(beta)))
    scenarios_out = []
    for sc in raw_scenarios:
        m_shock = float(sc["market_shock_pct"])
        # Unbuffered 100% risky equity impact
        risky_impact_pct = max(-0.95, min(0.0, effective_beta * m_shock))
        # Buffered complete portfolio impact (incorporating Cash / R_f weight)
        complete_impact_pct = max(-0.95, y_risky * risky_impact_pct)

        loss_vnd = abs(complete_impact_pct) * nav_vnd
        remaining_nav = max(0.0, nav_vnd - loss_vnd)
        unbuffered_loss_vnd = abs(risky_impact_pct) * nav_vnd
        cash_protection_vnd = max(0.0, unbuffered_loss_vnd - loss_vnd)

        scenarios_out.append({
            "id": sc["id"],
            "name": sc["name"],
            "period": sc["period"],
            "description": sc["description"],
            "market_shock_pct": m_shock,
            "risky_only_impact_pct": float(risky_impact_pct),
            "complete_impact_pct": float(complete_impact_pct),
            "estimated_loss_vnd": float(loss_vnd),
            "post_shock_nav_vnd": float(remaining_nav),
            "cash_protection_vnd": float(cash_protection_vnd),
        })

    return {
        "method": method_used,
        "nav_vnd": float(nav_vnd),
        "y_risky_weight": float(y_risky),
        "w_cash_weight": float(w_cash),
        "portfolio_beta": float(effective_beta),
        "var_metrics": {
            "var_95_1d_pct": float(var_95_1d),
            "var_95_1d_vnd": float(var_95_1d * nav_vnd),
            "var_99_1d_pct": float(var_99_1d),
            "var_99_1d_vnd": float(var_99_1d * nav_vnd),
            "cvar_95_1d_pct": float(cvar_95_1d),
            "cvar_95_1d_vnd": float(cvar_95_1d * nav_vnd),
            "cvar_99_1d_pct": float(cvar_99_1d),
            "cvar_99_1d_vnd": float(cvar_99_1d * nav_vnd),
            "var_95_21d_pct": float(var_95_21d),
            "var_95_21d_vnd": float(var_95_21d * nav_vnd),
            "var_99_21d_pct": float(var_99_21d),
            "var_99_21d_vnd": float(var_99_21d * nav_vnd),
            "cvar_95_21d_pct": float(cvar_95_21d),
            "cvar_95_21d_vnd": float(cvar_95_21d * nav_vnd),
            "max_drawdown_complete_pct": float(max_drawdown),
            "max_drawdown_risky_pct": float(max_drawdown_risky),
        },
        "scenarios": scenarios_out,
    }
