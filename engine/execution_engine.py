"""
Execution Accounting & Lot-100 Discretization Engine for Textbook MVO Workbench.
Single source of truth shared across FastAPI JSON, frontend UI tables/charts, and Excel export.

Invariants:
- Always executes strictly from Complete Portfolio target weights (w_comp_i = y_risky * w_risky[i]).
- Reserves buy fee (buy_fee_rate) inside lot sizing budget so purchase_value + buy_fee <= target_value.
- Enforces: nav_post_fee = nav_vnd - total_buy_fees == total_purchase_value + cash_remaining.
- Normalizes executed weights against nav_post_fee (actual_weights_post_fee + actual_cash_weight_post_fee == 1.0).
- Zero hidden price fallbacks: disables execution cleanly if prices are absent or short-selling is active.
"""
from __future__ import annotations

import math
from typing import Any


def compute_execution_plan(
    symbols: list[str],
    w_risky: list[float],
    y_risky: float,
    nav_vnd: float,
    latest_prices: dict[str, float | None] | None,
    price_dates: dict[str, str] | None = None,
    price_source_kind: str = "raw_close",  # "raw_close" | "uploaded_price" | "user_assumed" | "missing"
    w_min: float = 0.0,
    w_max: float = 1.0,
    lot_size: int = 100,
    buy_fee_rate: float = 0.0015,
    allow_short: bool = False,
) -> dict[str, Any]:
    """Compute realistic HOSE/HNX/UPCoM Lot-100 buy execution schedule with fee accounting."""
    n = len(symbols)
    nav_val = max(0.0, float(nav_vnd))
    y_val = max(0.0, float(y_risky))
    lot_sz = max(1, int(lot_size))
    fee_r = max(0.0, min(0.25, float(buy_fee_rate)))
    prices_map = latest_prices or {}
    dates_map = price_dates or {}

    base_payload = {
        "lot_size": lot_sz,
        "buy_fee_rate": fee_r,
        "price_source_kind": price_source_kind,
        "nav_vnd": nav_val,
        "y_risky": y_val,
        "target_cash_weight": max(0.0, 1.0 - y_val),
        "target_cash_vnd": nav_val * max(0.0, 1.0 - y_val),
    }

    if allow_short:
        return {
            **base_payload,
            "status": "disabled_short_mode",
            "disabled_reason": "Chế độ bán khống là tham chiếu học thuật; bảng mô phỏng mua lô chẵn 100 cổ phiếu được vô hiệu hóa.",
            "missing_price_symbols": [],
            "orders": [],
            "total_target_value": 0.0,
            "total_purchase_value": 0.0,
            "total_buy_fees": 0.0,
            "cash_remaining": nav_val,
            "nav_post_fee": nav_val,
            "actual_weights_post_fee": [0.0] * n,
            "actual_weights_initial_nav": [0.0] * n,
            "actual_cash_weight_post_fee": 1.0,
            "actual_equity_weights_within_basket": [0.0] * n,
            "bounds_drift_warnings": [],
        }

    # Verify required prices are present cleanly (never substitute synthetic fallback)
    missing_syms: list[str] = []
    any_valid_price = False
    for i, sym in enumerate(symbols):
        w_comp_i = y_val * float(w_risky[i])
        p_raw = prices_map.get(sym)
        is_valid_p = p_raw is not None and math.isfinite(float(p_raw)) and float(p_raw) > 0.0
        if is_valid_p:
            any_valid_price = True
        elif w_comp_i > 1e-8:
            missing_syms.append(sym)

    if price_source_kind == "missing" or (not any_valid_price and y_val <= 1e-8) or missing_syms:
        if not missing_syms:
            missing_syms = [
                sym for sym in symbols
                if prices_map.get(sym) is None or not math.isfinite(float(prices_map.get(sym, 0.0))) or float(prices_map.get(sym, 0.0)) <= 0.0
            ]
        return {
            **base_payload,
            "status": "disabled_no_prices",
            "disabled_reason": (
                f"Thiếu giá cổ phiếu hợp lệ cho mã: {', '.join(missing_syms)}. "
                "Chế độ ma trận tham số cần nhập giá giả định (> 0) nếu muốn mô phỏng chia lô."
                if missing_syms
                else "Chưa có giá cổ phiếu đầu vào để mô phỏng chia lô."
            ),
            "missing_price_symbols": missing_syms,
            "orders": [],
            "total_target_value": float(nav_val * y_val),
            "total_purchase_value": 0.0,
            "total_buy_fees": 0.0,
            "cash_remaining": nav_val,
            "nav_post_fee": nav_val,
            "actual_weights_post_fee": [0.0] * n,
            "actual_weights_initial_nav": [0.0] * n,
            "actual_cash_weight_post_fee": 1.0,
            "actual_equity_weights_within_basket": [0.0] * n,
            "bounds_drift_warnings": [],
        }

    orders: list[dict[str, Any]] = []
    for i, sym in enumerate(symbols):
        w_equity = max(0.0, float(w_risky[i]))
        w_comp = max(0.0, y_val * w_equity)
        target_val = nav_val * w_comp
        p_raw = prices_map.get(sym)
        p_val = float(p_raw) if (p_raw is not None and math.isfinite(float(p_raw)) and float(p_raw) > 0.0) else None
        p_date = dates_map.get(sym)

        if target_val <= 1e-9 or p_val is None:
            lots = 0
            shares = 0
            purchase_val = 0.0
            buy_fee = 0.0
        else:
            cost_per_lot = p_val * float(lot_sz) * (1.0 + fee_r)
            lots = int(math.floor((target_val / cost_per_lot) + 1e-12)) if cost_per_lot > 0 else 0
            lots = max(0, lots)
            shares = lots * lot_sz
            purchase_val = float(shares) * p_val
            buy_fee = purchase_val * fee_r

        orders.append({
            "symbol": sym,
            "w_equity_target": w_equity,
            "w_complete_target": w_comp,
            "target_value_vnd": target_val,
            "price_vnd": p_val,
            "price_date": p_date,
            "lots": lots,
            "shares": shares,
            "purchase_value_vnd": purchase_val,
            "buy_fee_vnd": buy_fee,
            "total_cash_out_vnd": purchase_val + buy_fee,
            "residual_from_target_vnd": target_val - purchase_val - buy_fee,
        })

    # Safety trim only if floating-point tie pushed total cash outlay slightly above NAV
    total_purchase = sum(o["purchase_value_vnd"] for o in orders)
    total_fees = sum(o["buy_fee_vnd"] for o in orders)
    if total_purchase + total_fees > nav_val + 1e-6:
        for o in sorted(orders, key=lambda x: x["lots"], reverse=True):
            if total_purchase + total_fees <= nav_val + 1e-6:
                break
            if o["lots"] > 0 and o["price_vnd"]:
                o["lots"] -= 1
                o["shares"] = o["lots"] * lot_sz
                o["purchase_value_vnd"] = float(o["shares"]) * o["price_vnd"]
                o["buy_fee_vnd"] = o["purchase_value_vnd"] * fee_r
                o["total_cash_out_vnd"] = o["purchase_value_vnd"] + o["buy_fee_vnd"]
                o["residual_from_target_vnd"] = o["target_value_vnd"] - o["total_cash_out_vnd"]
                total_purchase = sum(x["purchase_value_vnd"] for x in orders)
                total_fees = sum(x["buy_fee_vnd"] for x in orders)

    cash_remaining = max(0.0, nav_val - total_purchase - total_fees)
    nav_post_fee = nav_val - total_fees

    actual_weights_post_fee = []
    actual_weights_init_nav = []
    actual_equity_within_basket = []

    for o in orders:
        w_post = (o["purchase_value_vnd"] / nav_post_fee) if nav_post_fee > 1e-9 else 0.0
        w_init = (o["purchase_value_vnd"] / nav_val) if nav_val > 1e-9 else 0.0
        w_eq_act = (o["purchase_value_vnd"] / total_purchase) if total_purchase > 1e-9 else 0.0
        o["actual_weight_post_fee"] = w_post
        o["actual_weight_initial_nav"] = w_init
        o["actual_equity_weight"] = w_eq_act
        o["weight_drift_post_fee"] = w_post - o["w_complete_target"]
        actual_weights_post_fee.append(w_post)
        actual_weights_init_nav.append(w_init)
        actual_equity_within_basket.append(w_eq_act)

    actual_cash_post_fee = (cash_remaining / nav_post_fee) if nav_post_fee > 1e-9 else 1.0

    # Check if lot-100 rounding caused equity basket weights to drift outside [w_min, w_max]
    drift_warnings: list[dict[str, Any]] = []
    if total_purchase > 1e-9:
        for i, sym in enumerate(symbols):
            w_act_eq = actual_equity_within_basket[i]
            if w_act_eq > float(w_max) + 1e-4 or w_act_eq < float(w_min) - 1e-4:
                drift_warnings.append({
                    "symbol": sym,
                    "actual_equity_weight": w_act_eq,
                    "target_equity_weight": float(w_risky[i]),
                    "w_min": float(w_min),
                    "w_max": float(w_max),
                })

    return {
        **base_payload,
        "status": "ready",
        "disabled_reason": None,
        "missing_price_symbols": [],
        "orders": orders,
        "total_target_value": float(sum(o["target_value_vnd"] for o in orders)),
        "total_purchase_value": float(total_purchase),
        "total_buy_fees": float(total_fees),
        "cash_remaining": float(cash_remaining),
        "nav_post_fee": float(nav_post_fee),
        "actual_weights_post_fee": actual_weights_post_fee,
        "actual_weights_initial_nav": actual_weights_init_nav,
        "actual_cash_weight_post_fee": float(actual_cash_post_fee),
        "actual_equity_weights_within_basket": actual_equity_within_basket,
        "bounds_drift_warnings": drift_warnings,
    }
