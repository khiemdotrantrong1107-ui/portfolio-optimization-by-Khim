"""
Pure Textbook Mean-Variance Optimization (MVO) Mathematical Engine.
Implements Harry Markowitz (1952) and Robert Merton (1972) matrix algebra:
- 252 trading sessions annualization convention
- Unconstrained Closed-Form Analytical Solutions (Lagrange Multipliers, scalars A, B, C, D)
- Long-Only Constrained Quadratic Programming (SLSQP / Convex Optimization)
- Two-Fund Separation, Capital Allocation Line (CAL), Utility Maximization & Indifference Curves
- Monte Carlo Feasible Opportunity Set Simulation
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


def compute_moments_from_prices(
    df_prices: pd.DataFrame, trading_days: int = TRADING_DAYS
) -> dict[str, Any]:
    """Compute annualized sample mean, sample covariance, volatility, and correlation from daily prices."""
    df_clean = df_prices.dropna(how="any").sort_index()
    if len(df_clean) < 5:
        raise ValueError("Cần tối thiểu 5 phiên giao dịch hợp lệ để tính toán thống kê.")

    rets = df_clean.pct_change().dropna(how="any")
    symbols = list(df_clean.columns)

    mu_daily = rets.mean().to_numpy(dtype=float)
    cov_daily = rets.cov(ddof=1).to_numpy(dtype=float)

    mu_ann = mu_daily * float(trading_days)
    cov_ann = cov_daily * float(trading_days)
    std_ann = np.sqrt(np.maximum(np.diag(cov_ann), 1e-12))
    corr_mat = rets.corr().to_numpy(dtype=float)
    np.fill_diagonal(corr_mat, 1.0)

    latest_prices = {s: float(df_clean[s].iloc[-1]) for s in symbols}

    return {
        "symbols": symbols,
        "mu": mu_ann,
        "cov": cov_ann,
        "std": std_ann,
        "corr": corr_mat,
        "latest_prices": latest_prices,
        "sessions_count": len(rets),
        "daily_returns_df": rets,
        "prices_df": df_clean,
    }


def build_moments_from_manual(
    symbols: list[str],
    expected_returns: list[float],
    std_devs: list[float],
    corr_matrix: list[list[float]],
    latest_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Construct covariance matrix Sigma = D * P * D from textbook manual inputs."""
    n = len(symbols)
    if len(expected_returns) != n or len(std_devs) != n or len(corr_matrix) != n:
        raise ValueError("Kích thước vector lợi suất, độ lệch chuẩn và ma trận tương quan không khớp.")

    mu = np.array(expected_returns, dtype=float)
    std = np.array(std_devs, dtype=float)
    if np.any(std <= 0):
        raise ValueError("Độ lệch chuẩn (Volatility) của mọi tài sản phải lớn hơn 0.")

    corr = np.array(corr_matrix, dtype=float)
    if corr.shape != (n, n):
        raise ValueError(f"Ma trận tương quan phải có kích thước {n}x{n}.")

    # Symmetrize and validate correlation
    corr = 0.5 * (corr + corr.T)
    np.fill_diagonal(corr, 1.0)
    if np.any(corr < -1.0) or np.any(corr > 1.0):
        raise ValueError("Hệ số tương quan phải nằm trong đoạn [-1.0, +1.0].")

    cov = np.outer(std, std) * corr
    eigvals = np.linalg.eigvalsh(cov)
    if np.min(eigvals) < -1e-6:
        raise ValueError("Ma trận tương quan không hợp lệ (không bán xác định dương).")
    if np.min(eigvals) <= 1e-8:
        cov = cov + (abs(float(np.min(eigvals))) + 1e-6) * np.eye(n)

    prices = latest_prices or {s: 50_000.0 for s in symbols}

    return {
        "symbols": symbols,
        "mu": mu,
        "cov": cov,
        "std": std,
        "corr": corr,
        "latest_prices": prices,
        "sessions_count": TRADING_DAYS,
        "daily_returns_df": None,
        "prices_df": None,
    }


def _portfolio_stats(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> dict[str, float]:
    ret = float(np.dot(weights, mu))
    var = float(weights.T @ cov @ weights)
    vol = math.sqrt(max(var, 0.0))
    sharpe = (ret - rf) / vol if vol > 1e-8 else 0.0
    return {
        "expected_return": ret,
        "variance": var,
        "volatility": vol,
        "sharpe_ratio": sharpe,
    }


def solve_merton_closed_form(
    mu: np.ndarray, cov: np.ndarray, rf: float, num_frontier: int = 50
) -> dict[str, Any]:
    """
    Analytical Closed-Form Matrix Solution (Robert Merton 1972) when Short-Selling is Allowed.
    A = 1^T Sigma^-1 mu
    B = mu^T Sigma^-1 mu
    C = 1^T Sigma^-1 1
    D = B*C - A^2
    """
    n = len(mu)
    ones = np.ones(n, dtype=float)

    # Regularize slightly if near-singular
    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        inv_cov = np.linalg.pinv(cov + 1e-6 * np.eye(n))

    scalar_A = float(ones.T @ inv_cov @ mu)
    scalar_B = float(mu.T @ inv_cov @ mu)
    scalar_C = float(ones.T @ inv_cov @ ones)
    scalar_D = float(scalar_B * scalar_C - scalar_A**2)

    # 1. Global Minimum Variance (GMV)
    w_gmv = (inv_cov @ ones) / scalar_C
    gmv_stats = _portfolio_stats(w_gmv, mu, cov, rf)

    # 2. Tangency Portfolio (Maximum Sharpe Ratio)
    excess_mu = mu - rf * ones
    z_vec = inv_cov @ excess_mu
    sum_z = float( np.sum(z_vec) )
    if abs(sum_z) < 1e-8:
        w_tan = w_gmv.copy()
    else:
        w_tan = z_vec / sum_z

    tan_stats = _portfolio_stats(w_tan, mu, cov, rf)
    # Ensure tangency is on the upper branch; if Sharpe < GMV Sharpe, solve numerically on upper boundary
    if tan_stats["expected_return"] < gmv_stats["expected_return"] or tan_stats["sharpe_ratio"] < gmv_stats["sharpe_ratio"]:
        res_qp = solve_long_only_qp(mu, cov, rf, allow_short=True, num_frontier=num_frontier)
        w_tan = res_qp["w_tangency"]
        tan_stats = res_qp["tangency_stats"]

    # 3. Analytical Efficient Frontier Curve: w(E) = g + h * E
    # where g = (B*(Sigma^-1 1) - A*(Sigma^-1 mu)) / D, h = (C*(Sigma^-1 mu) - A*(Sigma^-1 1)) / D
    min_ret = gmv_stats["expected_return"] - 0.10
    max_ret = max(float(np.max(mu)), tan_stats["expected_return"]) + 0.15
    target_rets = np.linspace(min_ret, max_ret, num_frontier)

    frontier = []
    if scalar_D > 1e-10:
        g_vec = (scalar_B * (inv_cov @ ones) - scalar_A * (inv_cov @ mu)) / scalar_D
        h_vec = (scalar_C * (inv_cov @ mu) - scalar_A * (inv_cov @ ones)) / scalar_D
        for r_target in target_rets:
            w_p = g_vec + h_vec * r_target
            st = _portfolio_stats(w_p, mu, cov, rf)
            frontier.append({
                "return": st["expected_return"],
                "volatility": st["volatility"],
                "sharpe": st["sharpe_ratio"],
                "is_efficient": bool(r_target >= gmv_stats["expected_return"] - 1e-6),
                "weights": w_p.tolist(),
            })
    else:
        frontier.append({
            "return": gmv_stats["expected_return"],
            "volatility": gmv_stats["volatility"],
            "sharpe": gmv_stats["sharpe_ratio"],
            "is_efficient": True,
            "weights": w_gmv.tolist(),
        })

    return {
        "mode": "unconstrained_closed_form",
        "inv_cov": inv_cov,
        "merton_scalars": {
            "A": scalar_A,
            "B": scalar_B,
            "C": scalar_C,
            "D": scalar_D,
        },
        "w_gmv": w_gmv,
        "gmv_stats": gmv_stats,
        "w_tangency": w_tan,
        "tangency_stats": tan_stats,
        "frontier": frontier,
    }


def solve_long_only_qp(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    allow_short: bool = False,
    w_min: float = 0.0,
    w_max: float = 1.0,
    num_frontier: int = 50,
) -> dict[str, Any]:
    """
    Solve MVO via Quadratic Programming / SLSQP for Long-Only (w_i >= 0),
    Box-Constrained Institutional Mandates (w_min <= w_i <= w_max, e.g. Circular 98 max 20%),
    or bounded short-selling.
    """
    n = len(mu)
    init_w = np.ones(n) / n
    bounds_adjusted_note: str | None = None

    if allow_short:
        eff_min, eff_max = -1.0, 2.0
    else:
        req_min = max(0.0, float(w_min))
        req_max = min(1.0, float(w_max))
        equal_share = 1.0 / n

        if req_min > equal_share - 1e-4:
            eff_min = max(0.0, round(equal_share - 0.01, 4))
            bounds_adjusted_note = (
                f"Sàn tỷ trọng ({req_min*100:.1f}%) vượt quá mức chia đều {n} mã ({equal_share*100:.1f}%); "
                f"đã tự động điều chỉnh sàn về {eff_min*100:.1f}%."
            )
        else:
            eff_min = req_min

        if req_max < equal_share - 1e-5:
            eff_max = min(1.0, math.ceil(equal_share * 1000) / 1000.0)
            bounds_adjusted_note = (
                f"Trần tỷ trọng ({req_max*100:.1f}%) cho {n} mã chỉ đạt tối đa {req_max*n*100:.0f}% NAV; "
                f"đã tự động nâng trần lên {eff_max*100:.1f}% (cần tối thiểu {math.ceil(1.0/req_max)} mã cho trần {req_max*100:.0f}%)."
            )
        else:
            eff_max = req_max

        if eff_min > eff_max:
            eff_min = 0.0
            eff_max = 1.0

    bounds = [(eff_min, eff_max) for _ in range(n)]
    cons_sum1 = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    # 1. Global Minimum Variance (GMV)
    res_gmv = minimize(
        lambda w: 0.5 * float(w.T @ cov @ w),
        init_w,
        method="SLSQP",
        bounds=bounds,
        constraints=[cons_sum1],
        options={"ftol": 1e-11, "maxiter": 500},
    )
    w_gmv = res_gmv.x if res_gmv.success else init_w.copy()
    w_gmv = np.clip(w_gmv, eff_min, eff_max)
    if abs(float(np.sum(w_gmv)) - 1.0) > 1e-5:
        w_gmv = w_gmv / np.sum(w_gmv)
    gmv_stats = _portfolio_stats(w_gmv, mu, cov, rf)

    # 2. Maximum Sharpe Ratio (Tangency Portfolio)
    def _neg_sharpe(w: np.ndarray) -> float:
        ret = float(np.dot(w, mu))
        vol = math.sqrt(max(float(w.T @ cov @ w), 1e-12))
        return -(ret - rf) / vol

    res_tan = minimize(
        _neg_sharpe,
        w_gmv,
        method="SLSQP",
        bounds=bounds,
        constraints=[cons_sum1],
        options={"ftol": 1e-11, "maxiter": 500},
    )
    w_tan = res_tan.x if res_tan.success else w_gmv.copy()
    w_tan = np.clip(w_tan, eff_min, eff_max)
    if abs(float(np.sum(w_tan)) - 1.0) > 1e-5:
        w_tan = w_tan / np.sum(w_tan)
    tan_stats = _portfolio_stats(w_tan, mu, cov, rf)

    # 3. Efficient Frontier Curve (respecting box constraints [eff_min, eff_max])
    if not allow_short and (eff_min > 0.0 or eff_max < 1.0):
        res_min_r = minimize(
            lambda w: float(np.dot(w, mu)),
            init_w,
            method="SLSQP",
            bounds=bounds,
            constraints=[cons_sum1],
        )
        res_max_r = minimize(
            lambda w: -float(np.dot(w, mu)),
            init_w,
            method="SLSQP",
            bounds=bounds,
            constraints=[cons_sum1],
        )
        min_r = float(np.dot(res_min_r.x, mu)) if res_min_r.success else gmv_stats["expected_return"]
        max_r = float(np.dot(res_max_r.x, mu)) if res_max_r.success else tan_stats["expected_return"]
    else:
        min_r = float(np.min(mu)) if not allow_short else gmv_stats["expected_return"] - 0.08
        max_r = float(np.max(mu)) if not allow_short else max(float(np.max(mu)), tan_stats["expected_return"]) + 0.10

    if max_r <= min_r + 1e-6:
        target_rets = np.array([gmv_stats["expected_return"]])
    else:
        target_rets = np.linspace(min_r + 1e-5, max_r - 1e-5, num_frontier)

    frontier = []
    for r_t in target_rets:
        cons = [
            cons_sum1,
            {"type": "eq", "fun": lambda w, target=r_t: float(np.dot(w, mu)) - target},
        ]
        res_f = minimize(
            lambda w: 0.5 * float(w.T @ cov @ w),
            w_gmv,
            method="SLSQP",
            bounds=bounds,
            constraints=cons,
            options={"ftol": 1e-10, "maxiter": 300},
        )
        if res_f.success:
            w_f = np.clip(res_f.x, eff_min, eff_max)
            st = _portfolio_stats(w_f, mu, cov, rf)
            frontier.append({
                "return": st["expected_return"],
                "volatility": st["volatility"],
                "sharpe": st["sharpe_ratio"],
                "is_efficient": bool(st["expected_return"] >= gmv_stats["expected_return"] - 1e-5),
                "weights": w_f.tolist(),
            })

    if not frontier:
        frontier.append({
            "return": gmv_stats["expected_return"],
            "volatility": gmv_stats["volatility"],
            "sharpe": gmv_stats["sharpe_ratio"],
            "is_efficient": True,
            "weights": w_gmv.tolist(),
        })

    try:
        inv_cov = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        inv_cov = np.linalg.pinv(cov + 1e-6 * np.eye(n))

    ones = np.ones(n)
    scalar_A = float(ones.T @ inv_cov @ mu)
    scalar_B = float(mu.T @ inv_cov @ mu)
    scalar_C = float(ones.T @ inv_cov @ ones)
    scalar_D = float(scalar_B * scalar_C - scalar_A**2)

    return {
        "mode": "bounded_qp" if (not allow_short and (eff_min > 0.0 or eff_max < 1.0)) else ("long_only_qp" if not allow_short else "unconstrained_qp"),
        "effective_w_min": float(eff_min),
        "effective_w_max": float(eff_max),
        "bounds_adjusted_note": bounds_adjusted_note,
        "inv_cov": inv_cov,
        "merton_scalars": {
            "A": scalar_A,
            "B": scalar_B,
            "C": scalar_C,
            "D": scalar_D,
        },
        "w_gmv": w_gmv,
        "gmv_stats": gmv_stats,
        "w_tangency": w_tan,
        "tangency_stats": tan_stats,
        "frontier": frontier,
    }


def compute_complete_portfolio(
    tangency_stats: dict[str, float],
    w_tangency: np.ndarray,
    rf: float,
    risk_aversion_A: float,
    allow_leverage: bool = True,
    cash_mode: str = "bkm",
    mandated_cash_weight: float | None = None,
) -> dict[str, Any]:
    """
    Two-Fund Separation & Capital Allocation between Risk-Free Asset (Cash) and Risky Tangency Portfolio:
    - Mode 'bkm' (Academic Utility Maximization):
        U = E(R_c) - 0.5 * A * sigma_c^2
        y* = (E(R_tan) - R_f) / (A * sigma_tan^2), w_cash = 1 - y*
    - Mode 'mandated' (Institutional Cash Buffer / Tactical Asset Allocation):
        w_cash is explicitly set by the Portfolio Manager (e.g., 10% NAV),
        and risky equity basket receives y* = 1 - w_cash.
    """
    A_val = max(0.2, float(risk_aversion_A))
    er_tan = tangency_stats["expected_return"]
    var_tan = max(tangency_stats["variance"], 1e-10)
    vol_tan = tangency_stats["volatility"]

    y_star_bkm = (er_tan - rf) / (A_val * var_tan)
    if not allow_leverage:
        y_star_bkm = max(0.0, min(1.0, y_star_bkm))

    mode_clean = (cash_mode or "bkm").strip().lower()
    if mode_clean == "mandated" and mandated_cash_weight is not None:
        w_rf = max(0.0, min(0.95, float(mandated_cash_weight)))
        y_star = 1.0 - w_rf
    else:
        mode_clean = "bkm"
        y_star = y_star_bkm
        w_rf = 1.0 - y_star

    w_risky_assets = y_star * w_tangency

    er_complete = rf + y_star * (er_tan - rf)
    vol_complete = abs(y_star) * vol_tan
    var_complete = vol_complete**2
    utility_star = er_complete - 0.5 * A_val * var_complete

    # Capital Allocation Line (CAL) points from vol=0 to 1.6 * max(vol_tan, vol_complete)
    max_cal_vol = max(vol_tan, vol_complete, 0.25) * 1.4
    cal_vols = np.linspace(0.0, max_cal_vol, 30)
    slope_sr = tangency_stats["sharpe_ratio"]
    cal_points = [
        {"volatility": float(v), "return": float(rf + slope_sr * v)}
        for v in cal_vols
    ]

    # Indifference Curve: E(R) = U* + 0.5 * A * sigma^2
    indiff_points = [
        {"volatility": float(v), "return": float(utility_star + 0.5 * A_val * (v**2))}
        for v in cal_vols
    ]

    return {
        "cash_mode": mode_clean,
        "risk_aversion_A": A_val,
        "y_star_risky_weight": float(y_star),
        "y_star_bkm_theoretical": float(y_star_bkm),
        "w_rf_weight": float(w_rf),
        "asset_weights": w_risky_assets.tolist(),
        "expected_return": float(er_complete),
        "volatility": float(vol_complete),
        "variance": float(var_complete),
        "sharpe_ratio": float(slope_sr if y_star > 0 else 0.0),
        "utility_score": float(utility_star),
        "cal_line": cal_points,
        "indifference_curve": indiff_points,
    }


def simulate_monte_carlo(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    n_portfolios: int = 3000,
    allow_short: bool = False,
    seed: int = 42,
) -> list[dict[str, float]]:
    """Simulate random portfolios to visualize the Markowitz Feasible Set cloud."""
    rng = np.random.default_rng(seed)
    n = len(mu)

    if not allow_short:
        # Mix Dirichlet with flat and concentrated alphas to fill the entire boundary & interior
        n_half = n_portfolios // 2
        w1 = rng.dirichlet(np.ones(n), size=n_half)
        w2 = rng.dirichlet(np.full(n, 0.35), size=n_portfolios - n_half)
        weights_mat = np.vstack([w1, w2])
    else:
        raw = rng.normal(0.0, 1.0, size=(n_portfolios, n))
        row_sums = np.sum(raw, axis=1, keepdims=True)
        row_sums = np.where(np.abs(row_sums) < 0.2, 0.5, row_sums)
        weights_mat = raw / row_sums
        # Filter out extreme leverage so the scatter plot stays clean
        mask = np.max(np.abs(weights_mat), axis=1) <= 2.0
        weights_mat = weights_mat[mask]

    rets = weights_mat @ mu
    # Vectorized variance calculation: sum((W @ cov) * W, axis=1)
    vars_vec = np.einsum("ij,jk,ik->i", weights_mat, cov, weights_mat)
    vols = np.sqrt(np.maximum(vars_vec, 1e-12))
    sharpes = (rets - rf) / vols

    return [
        {
            "volatility": round(float(vols[i]) * 100, 3),
            "return": round(float(rets[i]) * 100, 3),
            "sharpe": round(float(sharpes[i]), 3),
        }
        for i in range(len(rets))
    ]
