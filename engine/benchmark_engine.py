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
from datetime import datetime
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

BENCHMARK_PRICE_TYPE = "Price Return Index (không bao gồm cổ tức)"
BENCHMARK_REBALANCE_NOTE = "Tái cân bằng hàng ngày về tỷ trọng mục tiêu, chưa trừ phí giao dịch"
BENCHMARK_EVAL_SCOPE = "In-Sample Historical (Đánh giá hồi tố với trọng số cố định — không phải kết quả out-of-sample)"


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
    Fetch daily closing levels for VNINDEX, VN30, HNX, or UPCOM from Local DB or VNDirect DChart API.
    Supports horizons: 6m, 1y, 2y, 3y, 5y, ytd, max.
    Never returns fabricated synthetic benchmark data on API error.
    """
    sym = (symbol or "VNINDEX").strip().upper()
    if sym not in ("VNINDEX", "VN30", "HNX", "UPCOM"):
        sym = "VNINDEX"
    rng_key = (range_str or "1y").strip().lower()
    cache_key = (sym, rng_key)

    now = time.time()
    if cache_key in _BENCHMARK_CACHE:
        ts, cached_series = _BENCHMARK_CACHE[cache_key]
        if now - ts < CACHE_TTL_SECONDS:
            return cached_series.copy()

    lookback_days = RANGE_DAYS_MAP.get(rng_key, 380)
    min_db_pts = {"6m": 80, "1y": 180, "2y": 360, "3y": 540, "5y": 900, "ytd": 15, "max": 180}.get(rng_key, 100)

    def _valid_db_benchmark() -> pd.Series | None:
        from engine import db_manager
        s_db = db_manager.get_benchmark_series_from_db(sym, lookback_days=lookback_days)
        if s_db is None or len(s_db) < min_db_pts:
            return None
        s_sliced = _slice_series_by_horizon(s_db, rng_key)
        if len(s_sliced) < 10:
            return None
        if rng_key == "ytd":
            first_dt = s_db.index[0].date()
            last_yr = s_db.index[-1].year
            if first_dt.year == last_yr and (first_dt.month > 1 or first_dt.day > 15):
                return None
        return s_sliced

    # 1. Check Local SQLite Database first when fresh & covering horizon (Zero Quota)
    try:
        s_fresh = _valid_db_benchmark()
        if s_fresh is not None and (datetime.now().date() - s_fresh.index[-1].date()).days <= 5:
            _BENCHMARK_CACHE[cache_key] = (now, s_fresh)
            return s_fresh.copy()
    except Exception:
        pass

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
            raise ValueError("Dữ liệu benchmark trả về quá ít phiên.")

        # Persist index series into local SQLite database
        try:
            from engine import db_manager
            db_manager.upsert_market_index_daily(sym, payload)
        except Exception:
            pass

        dates = pd.to_datetime(timestamps, unit="s", errors="coerce").normalize()
        s = pd.Series(pd.to_numeric(closes, errors="coerce"), index=dates, name=sym, dtype=float)
        s = s[s.index.notna()]
        s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
        s = s[np.isfinite(s.to_numpy(dtype=float)) & (s > 0)]
        s = _slice_series_by_horizon(s, rng_key)
        if len(s) < 10:
            raise ValueError("Chuỗi chỉ số benchmark sau làm sạch không đủ 10 phiên.")
        _BENCHMARK_CACHE[cache_key] = (now, s)
        return s.copy()
    except Exception as exc:
        # Offline fallback only if real cached market series exists in local SQLite
        try:
            s_db_fb = _valid_db_benchmark()
            if s_db_fb is not None:
                _BENCHMARK_CACHE[cache_key] = (now, s_db_fb)
                return s_db_fb.copy()
        except Exception:
            pass
        raise RuntimeError(f"Không thể tải dữ liệu chỉ số {sym} từ VNDirect DChart API ({exc}).") from exc


def sync_benchmark_index_to_db(symbol: str = "VNINDEX", range_str: str = "1y") -> dict[str, Any]:
    """
    Explicitly fetch and persist market index OHLCV from VNDirect DChart API into fact_market_indices_daily.
    Supported indices: VNINDEX, VN30, HNX, UPCOM.
    """
    sym = (symbol or "VNINDEX").strip().upper()
    if sym not in ("VNINDEX", "VN30", "HNX", "UPCOM"):
        raise ValueError(f"Chỉ số '{sym}' không được hỗ trợ. Vui lòng chọn VNINDEX, VN30, HNX hoặc UPCOM.")

    rng_key = (range_str or "1y").strip().lower()
    lookback_days = RANGE_DAYS_MAP.get(rng_key, 380)

    now = int(time.time())
    from_ts = now - (lookback_days * 86400)
    url = (
        f"https://dchart-api.vndirect.com.vn/dchart/history"
        f"?resolution=D&symbol={sym}&from={from_ts}&to={now}"
    )

    if HAS_CFFI:
        resp = cffi_requests.get(url, impersonate="chrome120", timeout=8)
        if resp.status_code != 200:
            raise RuntimeError(f"VNDirect DChart API trả về mã lỗi HTTP {resp.status_code}")
        payload = resp.json()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            payload = json.loads(r.read().decode("utf-8"))

    timestamps = payload.get("t", [])
    closes = payload.get("c", [])
    if not timestamps or not closes:
        raise ValueError(f"Không có dữ liệu lịch sử cho chỉ số {sym} trong khung thời gian {range_str}.")

    from engine import db_manager
    count = db_manager.upsert_market_index_daily(sym, payload)

    last_ts = timestamps[-1]
    last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d")
    last_close = float(closes[-1])

    return {
        "status": "success",
        "symbol": sym,
        "range": rng_key,
        "records_upserted": count,
        "latest_date": last_date,
        "latest_close": last_close,
        "source": "VNDirect DChart API",
    }


def compute_benchmark_comparison(
    df_asset_returns: pd.DataFrame | None,
    w_tangency: np.ndarray,
    tangency_stats: dict[str, float],
    rf: float,
    benchmark_symbol: str = "VNINDEX",
    range_str: str = "1y",
    optimization_range: str | None = None,
) -> dict[str, Any]:
    """
    Compute relative performance metrics of the Risky Reference Portfolio vs Benchmark (VN-Index / VN30)
    strictly on aligned calendar dates. Never fabricates parametric correlations or uses blind slice fallbacks.
    """
    bm_sym = (benchmark_symbol or "VNINDEX").strip().upper()
    if bm_sym not in ("VNINDEX", "VN30"):
        bm_sym = "VNINDEX"
    rng_key = (range_str or "1y").strip().lower()
    opt_rng_clean = (optimization_range or rng_key).strip().lower()
    bm_name = "VN-Index (HOSE Composite)" if bm_sym == "VNINDEX" else "VN30 Index (Large-Cap Bluechips)"

    def _unavailable(reason: str, message: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "unavailable_reason": reason,
            "message": message,
            "benchmark_symbol": bm_sym,
            "benchmark_range": rng_key.upper(),
            "benchmark_name": bm_name,
            "benchmark_price_type": BENCHMARK_PRICE_TYPE,
            "rebalance_assumption": BENCHMARK_REBALANCE_NOTE,
            "evaluation_scope": BENCHMARK_EVAL_SCOPE,
            "horizon_mismatch_warning": False,
            "sessions_compared": 0,
            "start_date": None,
            "end_date": None,
            "benchmark_return": None,
            "benchmark_volatility": None,
            "benchmark_sharpe": None,
            "portfolio_return": float(tangency_stats["expected_return"]),
            "portfolio_volatility": float(tangency_stats["volatility"]),
            "portfolio_sharpe": float(tangency_stats["sharpe_ratio"]),
            "active_return": None,
            "sharpe_spread": None,
            "beta": None,
            "jensen_alpha": None,
            "tracking_error": None,
            "information_ratio": None,
            "correlation": None,
            "r_squared": None,
            "cumulative_series": {
                "dates": [],
                "portfolio_base100": [],
                "benchmark_base100": [],
            },
        }

    if df_asset_returns is None or len(df_asset_returns) < 10:
        return _unavailable(
            "no_historical_returns",
            "Chế độ ma trận tham số không có chuỗi lợi suất lịch sử để tính Beta, Tracking Error hay đường tăng trưởng đối chiếu Benchmark.",
        )

    try:
        s_bm = fetch_benchmark_series(bm_sym, range_str=rng_key)
    except Exception as exc:
        return _unavailable("benchmark_api_error", str(exc))

    s_bm.index = pd.to_datetime(s_bm.index).normalize()
    r_bm = s_bm.pct_change().dropna()

    df_port_ret = df_asset_returns.copy()
    df_port_ret.index = pd.to_datetime(df_port_ret.index).normalize()
    df_port_ret = _slice_series_by_horizon(df_port_ret, rng_key)

    common_idx = df_port_ret.index.intersection(r_bm.index).sort_values()
    if len(common_idx) < 10:
        return _unavailable(
            "insufficient_aligned_sessions",
            f"Chỉ có {len(common_idx)} phiên trùng ngày giao dịch giữa danh mục và {bm_sym} (cần tối thiểu 10 phiên).",
        )

    w_arr = np.asarray(w_tangency, dtype=float)
    p_daily = (df_port_ret.loc[common_idx] @ w_arr).to_numpy(dtype=float, copy=True)
    m_daily = r_bm.loc[common_idx].to_numpy(dtype=float, copy=True)

    port_ret = float(np.mean(p_daily) * TRADING_DAYS)
    port_vol = float(np.std(p_daily, ddof=1) * math.sqrt(TRADING_DAYS))
    port_sr = (port_ret - rf) / port_vol if port_vol > 1e-8 else 0.0

    bm_ret = float(np.mean(m_daily) * TRADING_DAYS)
    bm_vol = float(np.std(m_daily, ddof=1) * math.sqrt(TRADING_DAYS))
    bm_sr = (bm_ret - rf) / bm_vol if bm_vol > 1e-8 else 0.0

    var_m = float(np.var(m_daily, ddof=1) * TRADING_DAYS)
    cov_pm = float(np.cov(p_daily, m_daily, ddof=1)[0, 1] * TRADING_DAYS) if len(p_daily) > 2 else 0.0
    beta = cov_pm / var_m if var_m > 1e-10 else 0.0

    corr_val = (
        float(np.corrcoef(p_daily, m_daily)[0, 1])
        if (np.std(p_daily) > 1e-10 and np.std(m_daily) > 1e-10)
        else 0.0
    )
    r_squared = corr_val**2

    active_daily = p_daily - m_daily
    tracking_error = float(np.std(active_daily, ddof=1) * math.sqrt(TRADING_DAYS))
    active_return = port_ret - bm_ret
    information_ratio = active_return / tracking_error if tracking_error > 1e-8 else 0.0
    jensen_alpha = port_ret - (rf + beta * (bm_ret - rf))

    # Anchor both wealth indices strictly at 100.00 on the same common base date prior to common_idx[0]
    prior_bm_dates = s_bm.index[s_bm.index < common_idx[0]]
    if len(prior_bm_dates) > 0:
        anchor_date = prior_bm_dates[-1]
    else:
        anchor_date = common_idx[0] - pd.tseries.offsets.BDay(1)

    dates_str = [anchor_date.strftime("%Y-%m-%d")] + [d.strftime("%Y-%m-%d") for d in common_idx]
    cum_port = [100.0] + (100.0 * np.cumprod(1.0 + p_daily)).round(2).tolist()
    cum_bm = [100.0] + (100.0 * np.cumprod(1.0 + m_daily)).round(2).tolist()

    return {
        "status": "available",
        "unavailable_reason": None,
        "message": None,
        "benchmark_symbol": bm_sym,
        "benchmark_range": rng_key.upper(),
        "benchmark_name": bm_name,
        "benchmark_price_type": BENCHMARK_PRICE_TYPE,
        "rebalance_assumption": BENCHMARK_REBALANCE_NOTE,
        "evaluation_scope": BENCHMARK_EVAL_SCOPE,
        "horizon_mismatch_warning": bool(rng_key != opt_rng_clean),
        "optimization_range": opt_rng_clean.upper(),
        "sessions_compared": int(len(common_idx)),
        "start_date": dates_str[0],
        "end_date": dates_str[-1],
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


def _compute_single_risk_profile(
    df_asset_returns: pd.DataFrame | None,
    w_equity: np.ndarray,
    y_risky: float,
    w_cash: float,
    comp_ret_ann: float,
    comp_vol_ann: float,
    nav_vnd: float,
    beta: float | None,
    rf: float,
    basis_label: str,
) -> dict[str, Any]:
    """Compute tail risk (1d & rolling 21d VaR/ES), MDD, and linear Beta stress scenarios for one portfolio basis."""
    daily_mu = comp_ret_ann / TRADING_DAYS
    daily_sigma = comp_vol_ann / math.sqrt(TRADING_DAYS)

    # Always compute Parametric Gaussian metrics cleanly
    p_var_95_1d_s = -(daily_mu - 1.6448536269514722 * daily_sigma)
    p_var_99_1d_s = -(daily_mu - 2.3263478740408408 * daily_sigma)
    p_es_95_1d_s = -daily_mu + 2.062712807507425 * daily_sigma
    p_es_99_1d_s = -daily_mu + 2.665214220345808 * daily_sigma

    sqrt_21 = math.sqrt(21.0)
    mu_21d = daily_mu * 21.0
    sig_21d = daily_sigma * sqrt_21
    p_var_95_21d_s = -(mu_21d - 1.6448536269514722 * sig_21d)
    p_var_99_21d_s = -(mu_21d - 2.3263478740408408 * sig_21d)
    p_es_95_21d_s = -mu_21d + 2.062712807507425 * sig_21d
    p_es_99_21d_s = -mu_21d + 2.665214220345808 * sig_21d

    n_obs = len(df_asset_returns) if df_asset_returns is not None else 0
    rolling_21d_obs = 0

    if df_asset_returns is not None and n_obs >= 20:
        r_risky_daily = (df_asset_returns @ w_equity).to_numpy(dtype=float, copy=True)
        r_comp_daily = y_risky * r_risky_daily + w_cash * (rf / TRADING_DAYS)

        # 1-day Historical VaR & ES with exact quantile slicing
        q_95 = float(np.percentile(r_comp_daily, 5))
        tail_95 = r_comp_daily[r_comp_daily <= q_95]
        var_95_1d_signed = -q_95
        es_95_1d_signed = -float(np.mean(tail_95)) if len(tail_95) > 0 else var_95_1d_signed
        var_95_1d = max(0.0, var_95_1d_signed)
        cvar_95_1d = max(0.0, es_95_1d_signed)

        q_99 = float(np.percentile(r_comp_daily, 1))
        tail_99 = r_comp_daily[r_comp_daily <= q_99]
        var_99_1d_signed = -q_99
        es_99_1d_signed = -float(np.mean(tail_99)) if len(tail_99) > 0 else var_99_1d_signed
        var_99_1d = max(0.0, var_99_1d_signed)
        cvar_99_1d = max(0.0, es_99_1d_signed)

        # True 21-day Rolling Compounded Historical VaR/ES (requires >= 41 daily sessions -> >= 21 windows)
        if n_obs >= 41:
            rolling_21d_obs = n_obs - 20
            gross = 1.0 + r_comp_daily
            r_21d = np.array(
                [float(np.prod(gross[t : t + 21]) - 1.0) for t in range(rolling_21d_obs)],
                dtype=float,
            )
            q21_95 = float(np.percentile(r_21d, 5))
            tail21_95 = r_21d[r_21d <= q21_95]
            var_95_21d_signed = -q21_95
            es_95_21d_signed = -float(np.mean(tail21_95)) if len(tail21_95) > 0 else var_95_21d_signed
            var_95_21d = max(0.0, var_95_21d_signed)
            cvar_95_21d = max(0.0, es_95_21d_signed)

            q21_99 = float(np.percentile(r_21d, 1))
            tail21_99 = r_21d[r_21d <= q21_99]
            var_99_21d_signed = -q21_99
            es_99_21d_signed = -float(np.mean(tail21_99)) if len(tail21_99) > 0 else var_99_21d_signed
            var_99_21d = max(0.0, var_99_21d_signed)
            cvar_99_21d = max(0.0, es_99_21d_signed)
            horizon_21d_method = "Historical Rolling 21-Session Compounded"
        else:
            var_95_21d = var_99_21d = cvar_95_21d = cvar_99_21d = None
            var_95_21d_signed = var_99_21d_signed = es_95_21d_signed = es_99_21d_signed = None
            horizon_21d_method = "unavailable_insufficient_sessions_for_21d"

        wealth_comp = np.cumprod(1.0 + r_comp_daily)
        peak_comp = np.maximum.accumulate(wealth_comp)
        dd_comp = (wealth_comp - peak_comp) / peak_comp
        max_drawdown = float(abs(np.min(dd_comp)))

        wealth_risky = np.cumprod(1.0 + r_risky_daily)
        peak_risky = np.maximum.accumulate(wealth_risky)
        dd_risky = (wealth_risky - peak_risky) / peak_risky
        max_drawdown_risky = float(abs(np.min(dd_risky)))

        method_used = "Historical Simulation"
        sample_warnings = []
        if n_obs < 60:
            sample_warnings.append(f"Cỡ mẫu {n_obs} phiên (< 60) có độ tin cậy thấp cho Historical VaR/ES 95%.")
        if n_obs < 100:
            sample_warnings.append(f"Cỡ mẫu {n_obs} phiên (< 100) khiến đuôi 99% chỉ có {len(tail_99)} quan sát.")
        if n_obs < 41:
            sample_warnings.append("Cần tối thiểu 41 phiên để tính Historical VaR/ES kỳ hạn 21 ngày trượt.")
    else:
        # Parametric Gaussian only (Matrix Mode or < 20 historical sessions): NO fake MDD or Historical Simulation
        var_95_1d_signed = p_var_95_1d_s
        var_99_1d_signed = p_var_99_1d_s
        es_95_1d_signed = p_es_95_1d_s
        es_99_1d_signed = p_es_99_1d_s

        var_95_1d = max(0.0, p_var_95_1d_s)
        var_99_1d = max(0.0, p_var_99_1d_s)
        cvar_95_1d = max(0.0, p_es_95_1d_s)
        cvar_99_1d = max(0.0, p_es_99_1d_s)

        var_95_21d_signed = p_var_95_21d_s
        var_99_21d_signed = p_var_99_21d_s
        es_95_21d_signed = p_es_95_21d_s
        es_99_21d_signed = p_es_99_21d_s

        var_95_21d = min(0.99, max(0.0, p_var_95_21d_s))
        var_99_21d = min(0.99, max(0.0, p_var_99_21d_s))
        cvar_95_21d = min(0.99, max(0.0, p_es_95_21d_s))
        cvar_99_21d = min(0.99, max(0.0, p_es_99_21d_s))

        max_drawdown = None
        max_drawdown_risky = None
        method_used = "Parametric Normal (i.i.d Gaussian)"
        horizon_21d_method = "Parametric Normal (iid sqrt(21))"
        sample_warnings = ["Không có chuỗi lịch sử đủ 20 phiên; chỉ hiển thị VaR/ES Tham số Chuẩn (không tính MDD/Historical VaR)."]

    # Beta Shock Stress Scenarios (only when empirical Beta is available)
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
            "description": "Bài kiểm tra sức chịu đựng tiêu chuẩn theo mô hình Beta khi thị trường giảm 15%.",
        },
    ]

    scenarios_out = []
    if df_asset_returns is None or beta is None:
        stress_status = "unavailable_no_beta_history"
        effective_beta = None
    else:
        stress_status = "available"
        effective_beta = max(0.0, min(3.0, float(beta)))
        for sc in raw_scenarios:
            m_shock = float(sc["market_shock_pct"])
            risky_impact_pct = max(-0.95, min(0.0, effective_beta * m_shock))
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

    def _opt_vnd(pct_val: float | None) -> float | None:
        return None if pct_val is None else float(pct_val * nav_vnd)

    return {
        "basis": basis_label,
        "method": method_used,
        "horizon_21d_method": horizon_21d_method,
        "nav_vnd": float(nav_vnd),
        "y_risky_weight": float(y_risky),
        "w_cash_weight": float(w_cash),
        "portfolio_beta": effective_beta,
        "stress_status": stress_status,
        "stress_model_note": "Mô hình cú sốc Beta tuyến tính 1 nhân tố dựa trên dữ liệu lịch sử đã căn chỉnh (chưa tính chi phí thanh khoản / tương quan phá vỡ khi khủng hoảng).",
        "sample_size": int(n_obs),
        "rolling_21d_obs": int(rolling_21d_obs),
        "sample_warnings": sample_warnings,
        "var_metrics": {
            "var_95_1d_pct": float(var_95_1d),
            "var_95_1d_vnd": float(var_95_1d * nav_vnd),
            "var_95_1d_signed_pct": float(var_95_1d_signed),
            "var_99_1d_pct": float(var_99_1d),
            "var_99_1d_vnd": float(var_99_1d * nav_vnd),
            "var_99_1d_signed_pct": float(var_99_1d_signed),
            "cvar_95_1d_pct": float(cvar_95_1d),
            "cvar_95_1d_vnd": float(cvar_95_1d * nav_vnd),
            "cvar_95_1d_signed_pct": float(es_95_1d_signed),
            "cvar_99_1d_pct": float(cvar_99_1d),
            "cvar_99_1d_vnd": float(cvar_99_1d * nav_vnd),
            "cvar_99_1d_signed_pct": float(es_99_1d_signed),
            "var_95_21d_pct": None if var_95_21d is None else float(var_95_21d),
            "var_95_21d_vnd": _opt_vnd(var_95_21d),
            "var_95_21d_signed_pct": None if var_95_21d_signed is None else float(var_95_21d_signed),
            "var_99_21d_pct": None if var_99_21d is None else float(var_99_21d),
            "var_99_21d_vnd": _opt_vnd(var_99_21d),
            "var_99_21d_signed_pct": None if var_99_21d_signed is None else float(var_99_21d_signed),
            "cvar_95_21d_pct": None if cvar_95_21d is None else float(cvar_95_21d),
            "cvar_95_21d_vnd": _opt_vnd(cvar_95_21d),
            "cvar_95_21d_signed_pct": None if es_95_21d_signed is None else float(es_95_21d_signed),
            "cvar_99_21d_pct": None if cvar_99_21d is None else float(cvar_99_21d),
            "cvar_99_21d_vnd": _opt_vnd(cvar_99_21d),
            "cvar_99_21d_signed_pct": None if es_99_21d_signed is None else float(es_99_21d_signed),
            "max_drawdown_complete_pct": max_drawdown,
            "max_drawdown_risky_pct": max_drawdown_risky,
            "parametric_1d": {
                "var_95_pct": float(max(0.0, p_var_95_1d_s)),
                "var_99_pct": float(max(0.0, p_var_99_1d_s)),
                "cvar_95_pct": float(max(0.0, p_es_95_1d_s)),
                "cvar_99_pct": float(max(0.0, p_es_99_1d_s)),
            },
            "parametric_21d": {
                "var_95_pct": float(min(0.99, max(0.0, p_var_95_21d_s))),
                "var_99_pct": float(min(0.99, max(0.0, p_var_99_21d_s))),
                "cvar_95_pct": float(min(0.99, max(0.0, p_es_95_21d_s))),
                "cvar_99_pct": float(min(0.99, max(0.0, p_es_99_21d_s))),
            },
        },
        "scenarios": scenarios_out,
    }


def compute_stress_testing_and_var(
    df_asset_returns: pd.DataFrame | None,
    w_tangency: np.ndarray,
    tangency_stats: dict[str, float],
    complete_stats: dict[str, Any],
    beta: float | None,
    nav_vnd: float,
    rf: float,
    execution_plan: dict[str, Any] | None = None,
    mu: np.ndarray | None = None,
    cov: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Compute Tail-Risk Metrics (VaR 95%/99%, ES/CVaR, Rolling 21d, MDD) and Beta Stress Scenarios
    for BOTH target_complete portfolio and executed_post_fee portfolio (when execution status is 'ready').
    """
    y_target = float(complete_stats.get("y_star_risky_weight", 1.0))
    w_cash_target = float(complete_stats.get("w_rf_weight", 1.0 - y_target))
    target_ret_ann = float(complete_stats.get("expected_return", tangency_stats["expected_return"]))
    target_vol_ann = float(complete_stats.get("volatility", tangency_stats["volatility"]))

    target_profile = _compute_single_risk_profile(
        df_asset_returns=df_asset_returns,
        w_equity=np.asarray(w_tangency, dtype=float),
        y_risky=y_target,
        w_cash=w_cash_target,
        comp_ret_ann=target_ret_ann,
        comp_vol_ann=target_vol_ann,
        nav_vnd=nav_vnd,
        beta=beta,
        rf=rf,
        basis_label="target_complete",
    )

    executed_profile = None
    if execution_plan and execution_plan.get("status") == "ready":
        w_eq_exec = np.asarray(execution_plan["actual_equity_weights_within_basket"], dtype=float)
        w_cash_exec = float(execution_plan["actual_cash_weight_post_fee"])
        y_exec = max(0.0, 1.0 - w_cash_exec)
        nav_post = float(execution_plan["nav_post_fee"])

        if mu is not None and cov is not None and y_exec > 1e-9:
            eq_ret_ex = float(np.dot(w_eq_exec, mu))
            eq_var_ex = max(0.0, float(w_eq_exec.T @ cov @ w_eq_exec))
            ex_ret_ann = rf + y_exec * (eq_ret_ex - rf)
            ex_vol_ann = y_exec * math.sqrt(eq_var_ex)
        else:
            ex_ret_ann = rf
            ex_vol_ann = 0.0

        executed_profile = _compute_single_risk_profile(
            df_asset_returns=df_asset_returns,
            w_equity=w_eq_exec,
            y_risky=y_exec,
            w_cash=w_cash_exec,
            comp_ret_ann=ex_ret_ann,
            comp_vol_ann=ex_vol_ann,
            nav_vnd=nav_post,
            beta=beta,
            rf=rf,
            basis_label="executed_post_fee",
        )

    return {
        **target_profile,
        "profiles": {
            "target_complete": target_profile,
            "executed_post_fee": executed_profile,
        },
    }
