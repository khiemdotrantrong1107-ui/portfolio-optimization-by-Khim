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

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


class InfeasibleConstraintsError(ValueError):
    """Raised when portfolio weight bounds cannot be satisfied mathematically without silent relaxation."""

    def __init__(self, code: str, message: str, suggestion: str | None = None):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        full_msg = f"{message} {suggestion}".strip() if suggestion else message
        super().__init__(full_msg)


def _check_cov_invertibility(cov: np.ndarray) -> tuple[bool, float, float]:
    """Return (is_invertible, min_eig, cond_number) without adding artificial jitter."""
    sym_cov = 0.5 * (cov + cov.T)
    eigvals = np.linalg.eigvalsh(sym_cov)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))
    if min_eig <= 1e-10:
        return False, min_eig, float("inf")
    cond = max_eig / min_eig
    return bool(cond < 1e10), min_eig, float(cond)


def _detect_duplicate_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    dups: list[str] = []
    for s in symbols:
        su = str(s).strip().upper()
        if su in seen and su not in dups:
            dups.append(su)
        seen.add(su)
    return dups


def validate_weight_bounds(
    n: int,
    w_min: float | list[float] | np.ndarray = 0.0,
    w_max: float | list[float] | np.ndarray = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Validate Long-Only box constraints l_i <= w_i <= u_i and sum(w_i) = 1.0 strictly.
    Never relaxes bounds silently; raises InfeasibleConstraintsError with actionable suggestions.
    """
    if np.ndim(w_min) == 0:
        l_vec = np.full(n, float(w_min), dtype=float)
    else:
        l_vec = np.asarray(w_min, dtype=float).ravel()
    if np.ndim(w_max) == 0:
        u_vec = np.full(n, float(w_max), dtype=float)
    else:
        u_vec = np.asarray(w_max, dtype=float).ravel()

    if len(l_vec) != n or len(u_vec) != n:
        raise InfeasibleConstraintsError(
            "bound_dimension_mismatch",
            f"Kích thước giới hạn tỷ trọng không khớp với {n} tài sản.",
        )

    if not np.all(np.isfinite(l_vec)) or not np.all(np.isfinite(u_vec)):
        raise InfeasibleConstraintsError(
            "non_finite_bounds",
            "Giới hạn tỷ trọng (sàn/trần) phải là số hữu hạn.",
        )

    if np.any(l_vec < -1e-9) or np.any(u_vec > 1.0 + 1e-9):
        raise InfeasibleConstraintsError(
            "invalid_bound_range",
            "Trong chế độ không bán khống (Long-Only), tỷ trọng từng cổ phiếu phải nằm trong [0%, 100%].",
        )

    l_vec = np.clip(l_vec, 0.0, 1.0)
    u_vec = np.clip(u_vec, 0.0, 1.0)

    bad_pair = np.where(l_vec > u_vec + 1e-9)[0]
    if len(bad_pair) > 0:
        idx = int(bad_pair[0])
        raise InfeasibleConstraintsError(
            "floor_above_ceiling",
            f"Sàn tỷ trọng ({l_vec[idx]*100:.1f}%) vượt quá trần ({u_vec[idx]*100:.1f}%).",
            "Vui lòng đặt sàn nhỏ hơn hoặc bằng trần.",
        )

    sum_max = float(np.sum(u_vec))
    if sum_max < 1.0 - 1e-7:
        max_u = float(np.max(u_vec))
        min_assets = math.ceil(1.0 / max_u) if max_u > 1e-9 else n + 1
        min_uniform_cap = (100.0 / n)
        raise InfeasibleConstraintsError(
            "max_sum_below_1",
            f"Tổng tỷ trọng tối đa của {n} mã chỉ đạt {sum_max*100:.1f}% (< 100%).",
            f"Cần tối thiểu {min_assets} mã ở mức trần hiện tại hoặc tăng trần lên tối thiểu {min_uniform_cap:.2f}%.",
        )

    sum_min = float(np.sum(l_vec))
    if sum_min > 1.0 + 1e-7:
        max_uniform_floor = 100.0 / n
        raise InfeasibleConstraintsError(
            "min_sum_above_1",
            f"Tổng tỷ trọng tối thiểu của {n} mã là {sum_min*100:.1f}% (> 100%).",
            f"Vui lòng giảm sàn mỗi mã xuống tối đa {max_uniform_floor:.2f}% hoặc giảm số lượng mã.",
        )

    return l_vec, u_vec


def _project_capped_simplex(v: np.ndarray, l_vec: np.ndarray, u_vec: np.ndarray) -> np.ndarray:
    """Euclidean projection onto {w : sum(w) = 1, l <= w <= u} via exact Lagrange multiplier bisection."""
    # Check bounds Feasibility
    if np.sum(u_vec) <= 1.0 + 1e-9:
        w = u_vec.copy()
        s = float(np.sum(w))
        return w / s if s > 0 else w
    if np.sum(l_vec) >= 1.0 - 1e-9:
        w = l_vec.copy()
        s = float(np.sum(w))
        return w / s if s > 0 else w

    lo = float(np.min(v - u_vec)) - 1.0
    hi = float(np.max(v - l_vec)) + 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        s = float(np.sum(np.clip(v - mid, l_vec, u_vec)))
        if s > 1.0:
            lo = mid
        else:
            hi = mid
    return np.clip(v - 0.5 * (lo + hi), l_vec, u_vec)


def _verify_weights(
    w: np.ndarray,
    l_vec: np.ndarray,
    u_vec: np.ndarray,
    cov: np.ndarray,
    tol: float = 1e-6,
) -> bool:
    if w is None or not np.all(np.isfinite(w)):
        return False
    if abs(float(np.sum(w)) - 1.0) > tol:
        return False
    if np.any(w < l_vec - tol) or np.any(w > u_vec + tol):
        return False
    var = float(w.T @ cov @ w)
    if not np.isfinite(var) or var < -1e-12:
        return False
    return True


def compute_moments_from_prices(
    df_prices: pd.DataFrame, trading_days: int = TRADING_DAYS
) -> dict[str, Any]:
    """Compute annualized sample mean, CAGR, sample covariance, volatility, and correlation from daily prices."""
    df_clean = df_prices.dropna(how="any").sort_index()
    if len(df_clean) < 5:
        raise ValueError("Cần tối thiểu 5 phiên giao dịch hợp lệ để tính toán thống kê.")

    vals = df_clean.to_numpy(dtype=float, copy=True)
    if not np.all(np.isfinite(vals)) or np.any(vals <= 0):
        raise ValueError("Chuỗi giá lịch sử chứa giá trị <= 0, NaN hoặc Inf.")

    rets = df_clean.pct_change().dropna(how="any")
    symbols = [str(s).strip().upper() for s in df_clean.columns]
    dups = _detect_duplicate_symbols(symbols)
    if dups:
        raise ValueError(f"Danh sách mã bị trùng lặp: {', '.join(dups)}.")

    mu_daily = rets.mean().to_numpy(dtype=float, copy=True)
    cov_daily = rets.cov(ddof=1).to_numpy(dtype=float, copy=True)

    mu_ann = mu_daily * float(trading_days)
    cov_ann = cov_daily * float(trading_days)
    cov_ann = 0.5 * (cov_ann + cov_ann.T)
    std_ann = np.sqrt(np.maximum(np.diag(cov_ann), 0.0))

    corr_mat = rets.corr().to_numpy(dtype=float, copy=True)
    corr_mat = np.nan_to_num(corr_mat, nan=0.0)
    np.fill_diagonal(corr_mat, 1.0)

    n_rets = len(rets)
    p_start = vals[0]
    p_end = vals[-1]
    cagr = np.power(p_end / p_start, float(trading_days) / float(max(n_rets, 1))) - 1.0

    is_cov_inv, min_eig, cond_num = _check_cov_invertibility(cov_ann)
    latest_prices = {symbols[i]: float(df_clean.iloc[-1, i]) for i in range(len(symbols))}

    return {
        "symbols": symbols,
        "mu": mu_ann,
        "cagr": cagr,
        "cov": cov_ann,
        "std": std_ann,
        "corr": corr_mat,
        "latest_prices": latest_prices,
        "sessions_count": int(n_rets),
        "daily_returns_df": rets,
        "prices_df": df_clean,
        "is_covariance_invertible": is_cov_inv,
        "min_eigenvalue": min_eig,
        "condition_number": cond_num,
        "return_metric": "arithmetic_annualized",
    }


def build_moments_from_manual(
    symbols: list[str],
    expected_returns: list[float],
    std_devs: list[float],
    corr_matrix: list[list[float]],
    latest_prices: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """
    Construct covariance matrix Sigma = D * P * D from textbook manual inputs.
    Strictly validates symmetry, unit diagonal, PSD condition, and finite positive prices without mutating inputs.
    """
    clean_syms = [str(s).strip().upper() for s in symbols]
    dups = _detect_duplicate_symbols(clean_syms)
    if dups:
        raise ValueError(f"Danh sách mã bị trùng lặp: {', '.join(dups)}.")

    n = len(clean_syms)
    if n < 2:
        raise ValueError("Cần tối thiểu 2 mã cổ phiếu hợp lệ.")
    if len(expected_returns) != n or len(std_devs) != n or len(corr_matrix) != n:
        raise ValueError("Kích thước vector lợi suất, độ lệch chuẩn và ma trận tương quan không khớp.")

    mu = np.array(expected_returns, dtype=float)
    std = np.array(std_devs, dtype=float)
    if not np.all(np.isfinite(mu)) or not np.all(np.isfinite(std)):
        raise ValueError("Lợi suất kỳ vọng và độ lệch chuẩn phải là số hữu hạn (không NaN/Inf).")
    if np.any(std <= 0):
        raise ValueError("Độ lệch chuẩn (Volatility) của mọi tài sản phải lớn hơn 0.")

    corr = np.array(corr_matrix, dtype=float)
    if corr.shape != (n, n):
        raise ValueError(f"Ma trận tương quan phải có kích thước {n}x{n}.")
    if not np.all(np.isfinite(corr)):
        raise ValueError("Ma trận tương quan chứa giá trị NaN hoặc Inf.")

    if np.max(np.abs(corr - corr.T)) > 1e-4:
        raise ValueError("Ma trận tương quan không đối xứng (|ρ_ij - ρ_ji| > 1e-4).")
    if np.max(np.abs(np.diag(corr) - 1.0)) > 1e-4:
        raise ValueError("Đường chéo chính của ma trận tương quan phải bằng 1.0.")

    if np.any(corr < -1.0 - 1e-6) or np.any(corr > 1.0 + 1e-6):
        raise ValueError("Hệ số tương quan phải nằm trong đoạn [-1.0, +1.0].")

    corr = 0.5 * (corr + corr.T)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)

    cov = np.outer(std, std) * corr
    cov = 0.5 * (cov + cov.T)
    eigvals = np.linalg.eigvalsh(cov)
    min_eig = float(np.min(eigvals))
    if min_eig < -1e-6:
        raise ValueError(
            f"Ma trận tương quan không hợp lệ (không bán xác định dương; trị riêng nhỏ nhất = {min_eig:.2e})."
        )

    is_cov_inv, min_eig, cond_num = _check_cov_invertibility(cov)

    prices_out: dict[str, float | None] = {}
    for sym in clean_syms:
        if latest_prices is not None and sym in latest_prices and latest_prices[sym] is not None:
            p_val = float(latest_prices[sym])
            if not math.isfinite(p_val) or p_val <= 0:
                raise ValueError(f"Giá hiện tại của mã '{sym}' phải là số hữu hạn > 0.")
            prices_out[sym] = p_val
        else:
            prices_out[sym] = None

    return {
        "symbols": clean_syms,
        "mu": mu,
        "cagr": None,
        "cov": cov,
        "std": std,
        "corr": corr,
        "latest_prices": prices_out,
        "sessions_count": None,
        "daily_returns_df": None,
        "prices_df": None,
        "is_covariance_invertible": is_cov_inv,
        "min_eigenvalue": min_eig,
        "condition_number": cond_num,
        "return_metric": "user_input_expected_return",
    }


def _portfolio_stats(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> dict[str, float]:
    ret = float(np.dot(weights, mu))
    var = max(0.0, float(weights.T @ cov @ weights))
    vol = math.sqrt(var)
    sharpe = (ret - rf) / vol if vol > 1e-8 else 0.0
    return {
        "expected_return": ret,
        "variance": var,
        "volatility": vol,
        "sharpe_ratio": sharpe,
    }


def solve_merton_closed_form(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    num_frontier: int = 50,
    _allow_qp_fallback: bool = True,
) -> dict[str, Any]:
    """
    Analytical Closed-Form Matrix Solution (Robert Merton 1972) when Short-Selling is Allowed.
    If Sigma is singular or near-singular, returns merton_status='singular_covariance' without fabricating an inverse.
    """
    n = len(mu)
    ones = np.ones(n, dtype=float)
    is_cov_inv, min_eig, cond_num = _check_cov_invertibility(cov)

    if not is_cov_inv:
        return {
            "mode": "unconstrained_closed_form",
            "merton_status": "singular_covariance",
            "is_covariance_invertible": False,
            "min_eigenvalue": min_eig,
            "condition_number": cond_num,
            "inv_cov": None,
            "merton_scalars": None,
            "w_gmv": None,
            "gmv_stats": None,
            "w_tangency": None,
            "tangency_stats": None,
            "tangency_status": "singular_covariance",
            "frontier": [],
            "message": "Ma trận hiệp phương sai suy biến (không khả nghịch); nghiệm giải tích Merton không xác định.",
        }

    inv_cov = np.linalg.inv(cov)

    scalar_A = float(ones.T @ inv_cov @ mu)
    scalar_B = float(mu.T @ inv_cov @ mu)
    scalar_C = float(ones.T @ inv_cov @ ones)
    scalar_D = float(scalar_B * scalar_C - scalar_A**2)

    w_gmv = (inv_cov @ ones) / scalar_C
    gmv_stats = _portfolio_stats(w_gmv, mu, cov, rf)

    excess_mu = mu - rf * ones
    if float(np.max(np.abs(excess_mu))) <= 1e-10:
        w_tan = w_gmv.copy()
        tan_stats = _portfolio_stats(w_tan, mu, cov, rf)
        tangency_status = "no_positive_excess_return"
    else:
        z_vec = inv_cov @ excess_mu
        sum_z = float(np.sum(z_vec))
        if abs(sum_z) < 1e-10:
            w_tan = w_gmv.copy()
            tan_stats = _portfolio_stats(w_tan, mu, cov, rf)
            tangency_status = "asymptotic_zero_sum_z"
        else:
            w_tan = z_vec / sum_z
            tan_stats = _portfolio_stats(w_tan, mu, cov, rf)
            if (
                _allow_qp_fallback
                and (
                    tan_stats["expected_return"] < gmv_stats["expected_return"] - 1e-8
                    or tan_stats["sharpe_ratio"] < gmv_stats["sharpe_ratio"] - 1e-8
                )
            ):
                res_qp = solve_long_only_qp(
                    mu, cov, rf, allow_short=True, num_frontier=num_frontier, _include_merton_ref=False
                )
                w_tan = res_qp["w_tangency"]
                tan_stats = res_qp["tangency_stats"]
                tangency_status = res_qp.get("tangency_status", "optimal")
            else:
                tangency_status = "optimal"

    frontier = []
    if scalar_D > 1e-10:
        r_start = gmv_stats["expected_return"]
        r_end = max(float(np.max(mu)), tan_stats["expected_return"]) + 0.12
        target_rets = np.linspace(r_start, max(r_end, r_start + 0.10), num_frontier)
        g_vec = (scalar_B * (inv_cov @ ones) - scalar_A * (inv_cov @ mu)) / scalar_D
        h_vec = (scalar_C * (inv_cov @ mu) - scalar_A * (inv_cov @ ones)) / scalar_D
        for r_target in target_rets:
            w_p = g_vec + h_vec * float(r_target)
            st = _portfolio_stats(w_p, mu, cov, rf)
            frontier.append({
                "return": st["expected_return"],
                "volatility": st["volatility"],
                "sharpe": st["sharpe_ratio"],
                "is_efficient": True,
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
        "merton_status": "available",
        "is_covariance_invertible": True,
        "min_eigenvalue": min_eig,
        "condition_number": cond_num,
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
        "tangency_status": tangency_status,
        "frontier": frontier,
        "message": None,
    }


def solve_long_only_qp(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    allow_short: bool = False,
    w_min: float | list[float] = 0.0,
    w_max: float | list[float] = 1.0,
    num_frontier: int = 50,
    _include_merton_ref: bool = True,
) -> dict[str, Any]:
    """
    Solve MVO via Quadratic Programming / SLSQP for Long-Only (w_min <= w_i <= w_max)
    or bounded short-selling. Never alters or relaxes infeasible user bounds.
    """
    n = len(mu)
    if allow_short:
        l_vec = np.full(n, -1.0, dtype=float)
        u_vec = np.full(n, 2.0, dtype=float)
    else:
        l_vec, u_vec = validate_weight_bounds(n, w_min, w_max)

    eff_min = float(np.min(l_vec))
    eff_max = float(np.max(u_vec))
    bounds = [(float(l_vec[i]), float(u_vec[i])) for i in range(n)]
    cons_sum1 = {"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}
    init_w = _project_capped_simplex(np.ones(n, dtype=float) / n, l_vec, u_vec)

    is_singleton = bool(
        not allow_short
        and (
            float(np.sum(u_vec)) <= 1.0 + 1e-9
            or float(np.sum(l_vec)) >= 1.0 - 1e-9
            or float(np.sum(u_vec - l_vec)) <= 1e-9
        )
    )

    # Analytical Merton reference (never fails QP if cov is PSD singular)
    if _include_merton_ref:
        merton_ref = solve_merton_closed_form(mu, cov, rf, num_frontier=num_frontier, _allow_qp_fallback=False)
    else:
        is_inv, _, _ = _check_cov_invertibility(cov)
        merton_ref = {
            "is_covariance_invertible": is_inv,
            "merton_status": "skipped",
            "inv_cov": None,
            "merton_scalars": None,
        }

    if is_singleton:
        w_unique = init_w.copy()
        if not _verify_weights(w_unique, l_vec, u_vec, cov):
            raise RuntimeError("Hậu kiểm điểm khả thi duy nhất thất bại.")
        stats_unique = _portfolio_stats(w_unique, mu, cov, rf)
        has_pos_excess = stats_unique["expected_return"] > rf + 1e-8
        tan_status = "optimal" if has_pos_excess else "no_positive_excess_return"
        pt = {
            "return": stats_unique["expected_return"],
            "volatility": stats_unique["volatility"],
            "sharpe": stats_unique["sharpe_ratio"],
            "is_efficient": True,
            "weights": w_unique.tolist(),
        }
        return {
            "mode": "bounded_qp",
            "effective_w_min": eff_min,
            "effective_w_max": eff_max,
            "bounds_adjusted_note": None,
            "is_singleton": True,
            "is_covariance_invertible": merton_ref["is_covariance_invertible"],
            "merton_status": merton_ref["merton_status"],
            "merton_reference": merton_ref,
            "inv_cov": merton_ref["inv_cov"],
            "merton_scalars": merton_ref["merton_scalars"],
            "w_gmv": w_unique,
            "gmv_stats": stats_unique,
            "w_tangency": w_unique,
            "tangency_stats": stats_unique,
            "tangency_status": tan_status,
            "has_positive_excess_return": has_pos_excess,
            "frontier": [pt],
        }

    # 1. Global Minimum Variance (GMV)
    res_gmv = minimize(
        lambda w: 0.5 * float(w.T @ cov @ w),
        init_w,
        method="SLSQP",
        bounds=bounds,
        constraints=[cons_sum1],
        options={"ftol": 1e-12, "maxiter": 600},
    )
    w_gmv = _project_capped_simplex(res_gmv.x, l_vec, u_vec) if res_gmv.success else init_w.copy()
    if not _verify_weights(w_gmv, l_vec, u_vec, cov):
        raise RuntimeError("Không tìm thấy nghiệm GMV hợp lệ thỏa mãn ràng buộc.")
    gmv_stats = _portfolio_stats(w_gmv, mu, cov, rf)

    # 2. Feasible Return Range [min_feasible_ret, max_feasible_ret]
    res_min_r = minimize(
        lambda w: float(np.dot(w, mu)),
        init_w,
        method="SLSQP",
        bounds=bounds,
        constraints=[cons_sum1],
        options={"ftol": 1e-11, "maxiter": 400},
    )
    res_max_r = minimize(
        lambda w: -float(np.dot(w, mu)),
        init_w,
        method="SLSQP",
        bounds=bounds,
        constraints=[cons_sum1],
        options={"ftol": 1e-11, "maxiter": 400},
    )
    w_min_r = _project_capped_simplex(res_min_r.x, l_vec, u_vec) if res_min_r.success else w_gmv.copy()
    w_max_r = _project_capped_simplex(res_max_r.x, l_vec, u_vec) if res_max_r.success else w_gmv.copy()

    min_feasible_ret = float(np.dot(w_min_r, mu))
    max_feasible_ret = float(np.dot(w_max_r, mu))
    if allow_short:
        max_feasible_ret = max(max_feasible_ret, float(np.max(mu)) + 0.10)

    has_positive_excess = bool(max_feasible_ret > rf + 1e-8)

    # 3. Maximum Sharpe Ratio (Tangency / Reference Max-Sharpe Portfolio)
    if (max_feasible_ret - min_feasible_ret) <= 1e-10:
        w_tan = w_gmv.copy()
    else:
        def _neg_sharpe(w: np.ndarray) -> float:
            ret = float(np.dot(w, mu))
            vol = math.sqrt(max(float(w.T @ cov @ w), 1e-12))
            return -(ret - rf) / vol

        candidates = [w_gmv, w_max_r]
        best_w = w_gmv.copy()
        best_val = _neg_sharpe(best_w)
        for start_w in candidates:
            res_tan = minimize(
                _neg_sharpe,
                start_w,
                method="SLSQP",
                bounds=bounds,
                constraints=[cons_sum1],
                options={"ftol": 1e-12, "maxiter": 600},
            )
            if res_tan.success:
                cand_w = _project_capped_simplex(res_tan.x, l_vec, u_vec)
                if _verify_weights(cand_w, l_vec, u_vec, cov):
                    val = _neg_sharpe(cand_w)
                    if val < best_val:
                        best_val = val
                        best_w = cand_w
        # Check extreme w_max_r too in case Sharpe slope prefers boundary
        if _verify_weights(w_max_r, l_vec, u_vec, cov) and _neg_sharpe(w_max_r) < best_val:
            best_w = w_max_r
        w_tan = best_w

    if not _verify_weights(w_tan, l_vec, u_vec, cov):
        raise RuntimeError("Nghiệm danh mục tiếp tuyến không đạt hậu kiểm ràng buộc.")
    tan_stats = _portfolio_stats(w_tan, mu, cov, rf)
    tangency_status = "optimal" if has_positive_excess else "no_positive_excess_return"

    # 4. Efficient Frontier Curve (upper efficient branch ONLY: r_gmv -> max_feasible_ret)
    r_gmv = gmv_stats["expected_return"]
    r_top = max(r_gmv, float(np.dot(w_max_r, mu)))
    if allow_short:
        r_top = max(r_top, tan_stats["expected_return"]) + 0.08

    frontier: list[dict[str, Any]] = []
    if r_top <= r_gmv + 1e-7:
        frontier.append({
            "return": gmv_stats["expected_return"],
            "volatility": gmv_stats["volatility"],
            "sharpe": gmv_stats["sharpe_ratio"],
            "is_efficient": True,
            "weights": w_gmv.tolist(),
        })
    else:
        target_rets = np.linspace(r_gmv, r_top, num_frontier)
        prev_w = w_gmv.copy()
        prev_vol = gmv_stats["volatility"]
        for idx_f, r_t in enumerate(target_rets):
            if idx_f == 0:
                w_pt = w_gmv.copy()
            elif idx_f == len(target_rets) - 1 and not allow_short:
                w_pt = w_max_r.copy()
            else:
                cons = [
                    cons_sum1,
                    {"type": "eq", "fun": lambda w, target=float(r_t): float(np.dot(w, mu)) - target},
                ]
                res_f = minimize(
                    lambda w: 0.5 * float(w.T @ cov @ w),
                    prev_w,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=cons,
                    options={"ftol": 1e-11, "maxiter": 400},
                )
                if not res_f.success:
                    continue
                w_pt = _project_capped_simplex(res_f.x, l_vec, u_vec)

            if not _verify_weights(w_pt, l_vec, u_vec, cov):
                continue
            st = _portfolio_stats(w_pt, mu, cov, rf)
            if st["expected_return"] < r_gmv - 1e-7:
                continue
            if st["volatility"] < prev_vol - 1e-6:
                continue
            prev_w = w_pt
            prev_vol = max(prev_vol, st["volatility"])
            frontier.append({
                "return": st["expected_return"],
                "volatility": st["volatility"],
                "sharpe": st["sharpe_ratio"],
                "is_efficient": True,
                "weights": w_pt.tolist(),
            })

    if not frontier:
        frontier.append({
            "return": gmv_stats["expected_return"],
            "volatility": gmv_stats["volatility"],
            "sharpe": gmv_stats["sharpe_ratio"],
            "is_efficient": True,
            "weights": w_gmv.tolist(),
        })

    return {
        "mode": "bounded_qp" if (not allow_short and (eff_min > 0.0 or eff_max < 1.0)) else ("long_only_qp" if not allow_short else "unconstrained_qp"),
        "effective_w_min": eff_min,
        "effective_w_max": eff_max,
        "bounds_adjusted_note": None,
        "is_singleton": False,
        "is_covariance_invertible": merton_ref["is_covariance_invertible"],
        "merton_status": merton_ref["merton_status"],
        "merton_reference": merton_ref,
        "inv_cov": merton_ref["inv_cov"],
        "merton_scalars": merton_ref["merton_scalars"],
        "w_gmv": w_gmv,
        "gmv_stats": gmv_stats,
        "w_tangency": w_tan,
        "tangency_stats": tan_stats,
        "tangency_status": tangency_status,
        "has_positive_excess_return": has_positive_excess,
        "frontier": frontier,
    }


def compute_complete_portfolio(
    tangency_stats: dict[str, float],
    w_tangency: np.ndarray,
    rf: float,
    risk_aversion_A: float = 3.0,
    risk_aversion_gamma: float | None = None,
    allow_leverage: bool = False,
    cash_mode: str = "utility_no_leverage",
    mandated_cash_weight: float | None = None,
    tangency_status: str = "optimal",
) -> dict[str, Any]:
    """
    Two-Fund Capital Allocation between Risk-Free Asset (Cash) and Reference Risky Portfolio.
    - utility_no_leverage ('bkm'): maximizes U = E(R_c) - 0.5 * gamma * sigma_c^2 along the CAL ray y in [0, 1].
      When all feasible portfolios have E(R) <= Rf ('no_positive_excess_return'), utility_no_leverage assigns y* = 0 (100% Cash).
    - fixed_cash ('mandated'): allocates fixed w_cash in [0, 1] and y = 1 - w_cash into the risky portfolio.
    """
    gamma = max(0.2, float(risk_aversion_gamma if risk_aversion_gamma is not None else risk_aversion_A))
    er_tan = float(tangency_stats["expected_return"])
    var_tan = max(0.0, float(tangency_stats["variance"]))
    vol_tan = float(tangency_stats["volatility"])

    if tangency_status == "no_positive_excess_return" or er_tan <= rf + 1e-8:
        if var_tan > 1e-12:
            y_raw = (er_tan - rf) / (gamma * var_tan)
        else:
            y_raw = 0.0
        y_utility = 0.0 if not allow_leverage else y_raw
        clamp_reason = "no_positive_excess_return" if not allow_leverage else "unclamped"
    elif var_tan <= 1e-12:
        # Degenerate zero-variance portfolio strictly beating Rf -> 100% risky when no leverage
        y_raw = 1.0
        y_utility = 1.0
        clamp_reason = "zero_variance_dominant"
    else:
        y_raw = (er_tan - rf) / (gamma * var_tan)
        if not allow_leverage:
            if y_raw <= 0.0:
                y_utility = 0.0
                clamp_reason = "clamped_to_zero"
            elif y_raw >= 1.0:
                y_utility = 1.0
                clamp_reason = "clamped_to_one_no_leverage"
            else:
                y_utility = y_raw
                clamp_reason = "unclamped"
        else:
            y_utility = y_raw
            clamp_reason = "unclamped"

    mode_in = (cash_mode or "bkm").strip().lower()
    is_fixed_cash = mode_in in ("mandated", "fixed_cash") and mandated_cash_weight is not None

    if is_fixed_cash:
        w_rf = max(0.0, min(1.0, float(mandated_cash_weight)))
        y_star = 1.0 - w_rf
        mode_canonical = "fixed_cash"
        mode_api = "mandated" if mode_in == "mandated" else "fixed_cash"
        clamp_reason_out = "fixed_cash_override"
        is_utility_opt = False
    else:
        y_star = float(y_utility)
        w_rf = 1.0 - y_star
        mode_canonical = "utility_with_leverage" if allow_leverage else "utility_no_leverage"
        mode_api = "bkm" if mode_in == "bkm" else mode_canonical
        clamp_reason_out = clamp_reason
        is_utility_opt = True

    w_risky_assets = y_star * np.asarray(w_tangency, dtype=float)

    er_complete = rf + y_star * (er_tan - rf)
    vol_complete = abs(y_star) * vol_tan
    var_complete = vol_complete**2
    utility_star = er_complete - 0.5 * gamma * var_complete

    max_cal_vol = max(vol_tan, vol_complete, 0.25) * 1.4
    cal_vols = np.linspace(0.0, max_cal_vol, 30)
    slope_sr = float(tangency_stats["sharpe_ratio"])
    cal_points = [
        {"volatility": float(v), "return": float(rf + slope_sr * v)}
        for v in cal_vols
    ]
    indiff_points = [
        {"volatility": float(v), "return": float(utility_star + 0.5 * gamma * (v**2))}
        for v in cal_vols
    ]

    return {
        "cash_mode": mode_api,
        "cash_mode_canonical": mode_canonical,
        "is_utility_optimal": is_utility_opt,
        "tangency_status": tangency_status,
        "no_positive_excess_warning": bool(tangency_status == "no_positive_excess_return"),
        "clamp_reason": clamp_reason_out,
        "risk_aversion_A": gamma,
        "risk_aversion_gamma": gamma,
        "y_star_risky_weight": float(y_star),
        "y_star_bkm_theoretical": float(y_utility),
        "y_star_unconstrained": float(y_raw),
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


def _derive_mc_seed(
    n: int,
    w_min: float,
    w_max: float,
    mu: np.ndarray,
    allow_short: bool,
    symbols: list[str] | None = None,
) -> int:
    payload = "|".join([
        ",".join(symbols) if symbols else str(n),
        f"{w_min:.6f}",
        f"{w_max:.6f}",
        ",".join(f"{float(x):.6f}" for x in mu),
        "1" if allow_short else "0",
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def simulate_monte_carlo(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float,
    n_portfolios: int = 3000,
    allow_short: bool = False,
    w_min: float | list[float] = 0.0,
    w_max: float | list[float] = 1.0,
    seed: int | None = None,
    symbols: list[str] | None = None,
    anchor_weights: list[np.ndarray] | None = None,
) -> dict[str, Any]:
    """
    Simulate random portfolios strictly inside the optimizer's feasible region.
    Uses Sequential Conditional Interval Sampling on box-constrained simplex [l_vec, u_vec]
    mixed with convex combinations of anchor portfolios, returning 1 point when the polytope is a singleton.
    """
    n = len(mu)
    if seed is None:
        eff_min_s = float(np.min(w_min)) if np.ndim(w_min) > 0 else float(w_min)
        eff_max_s = float(np.max(w_max)) if np.ndim(w_max) > 0 else float(w_max)
        seed = _derive_mc_seed(n, eff_min_s, eff_max_s, mu, allow_short, symbols=symbols)

    rng = np.random.default_rng(seed)

    if allow_short:
        raw = rng.normal(0.0, 1.0, size=(n_portfolios, n))
        row_sums = np.sum(raw, axis=1, keepdims=True)
        row_sums = np.where(np.abs(row_sums) < 0.2, 0.5, row_sums)
        weights_mat = raw / row_sums
        mask = np.max(np.abs(weights_mat), axis=1) <= 2.0
        weights_mat = weights_mat[mask]
        is_singleton = False
        eff_min_out, eff_max_out = -1.0, 2.0
    else:
        l_vec, u_vec = validate_weight_bounds(n, w_min, w_max)
        eff_min_out = float(np.min(l_vec))
        eff_max_out = float(np.max(u_vec))
        is_singleton = bool(
            float(np.sum(u_vec)) <= 1.0 + 1e-9
            or float(np.sum(l_vec)) >= 1.0 - 1e-9
            or float(np.sum(u_vec - l_vec)) <= 1e-9
        )

        if is_singleton:
            w_only = _project_capped_simplex(np.ones(n) / n, l_vec, u_vec)
            weights_mat = w_only.reshape(1, n)
        else:
            samples: list[np.ndarray] = []
            # Ensure feasible anchor portfolios and extreme convex combinations are included
            anchors_valid: list[np.ndarray] = []
            if anchor_weights:
                for aw in anchor_weights:
                    arr = np.asarray(aw, dtype=float)
                    if len(arr) == n and _verify_weights(arr, l_vec, u_vec, cov):
                        anchors_valid.append(arr)
                        samples.append(arr)

            n_anchor_blends = min(len(anchors_valid) * 40, n_portfolios // 10) if len(anchors_valid) >= 2 else 0
            for _ in range(n_anchor_blends):
                idx_a, idx_b = rng.choice(len(anchors_valid), size=2, replace=False)
                alpha = float(rng.uniform(0.0, 1.0))
                w_blend = alpha * anchors_valid[idx_a] + (1.0 - alpha) * anchors_valid[idx_b]
                samples.append(w_blend)

            n_random = max(1, n_portfolios - len(samples))
            for s_idx in range(n_random):
                perm = rng.permutation(n)
                w_sample = np.zeros(n, dtype=float)
                rem_sum = 1.0
                rem_l = float(np.sum(l_vec))
                rem_u = float(np.sum(u_vec))
                use_beta = (s_idx % 2 == 1)

                for k in range(n - 1):
                    idx = int(perm[k])
                    rem_l_rest = rem_l - float(l_vec[idx])
                    rem_u_rest = rem_u - float(u_vec[idx])
                    low_k = max(float(l_vec[idx]), rem_sum - rem_u_rest)
                    high_k = min(float(u_vec[idx]), rem_sum - rem_l_rest)
                    if high_k <= low_k + 1e-12:
                        val_k = 0.5 * (low_k + high_k)
                    elif use_beta:
                        val_k = low_k + (high_k - low_k) * float(rng.beta(0.35, 0.35))
                    else:
                        val_k = float(rng.uniform(low_k, high_k))
                    val_k = float(np.clip(val_k, l_vec[idx], u_vec[idx]))
                    w_sample[idx] = val_k
                    rem_sum -= val_k
                    rem_l = rem_l_rest
                    rem_u = rem_u_rest

                last_idx = int(perm[n - 1])
                w_sample[last_idx] = float(np.clip(rem_sum, l_vec[last_idx], u_vec[last_idx]))
                if _verify_weights(w_sample, l_vec, u_vec, cov):
                    samples.append(w_sample)

            weights_mat = np.vstack(samples) if samples else _project_capped_simplex(np.ones(n) / n, l_vec, u_vec).reshape(1, n)

    rets = weights_mat @ mu
    vars_vec = np.einsum("ij,jk,ik->i", weights_mat, cov, weights_mat)
    vols = np.sqrt(np.maximum(vars_vec, 0.0))
    sharpes = np.where(vols > 1e-8, (rets - rf) / vols, 0.0)

    points = [
        {
            "volatility": round(float(vols[i]) * 100.0, 3),
            "return": round(float(rets[i]) * 100.0, 3),
            "sharpe": round(float(sharpes[i]), 3),
        }
        for i in range(len(rets))
    ]
    return {
        "points": points,
        "is_singleton": is_singleton,
        "seed": int(seed),
        "count": len(points),
        "w_min": eff_min_out,
        "w_max": eff_max_out,
    }
