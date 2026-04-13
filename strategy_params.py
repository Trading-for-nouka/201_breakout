# strategy_params.py
# バックテスト実績値に基づく戦略別パラメータ定数
# 2015-2025 日本大型株ユニバース実績

STRATEGY_PARAMS = {

    # ============================================================
    # ブレイクアウト戦略（scan.py）
    # 実績: 勝率53% / PF1.25 / 保有21日
    # ============================================================
    "breakout": {
        "entry_atr_low":    0.0,
        "entry_atr_high":   0.3,
        "stop_atr_mult":    1.5,
        "target_rr":        2.0,
        "hold_days":        21,
        "win_rate":         0.53,
        "profit_factor":    1.25,
    },

    # ============================================================
    # 押し目買い戦略（scan_dip.py）
    # 実績: 勝率53.5% / PF1.25 / 保有10日 / 平均リターン+0.427%
    # ============================================================
    "dip": {
        "dev_lower":        -0.05,
        "dev_upper":        +0.05,
        "stop_atr_mult":    1.5,
        "hold_days":        10,
        "win_rate":         0.535,
        "profit_factor":    1.25,
        "avg_return_10d":   0.00427,
    },
}


def calc_breakout_levels(close, atr14):
    p = STRATEGY_PARAMS["breakout"]
    entry_low  = close + p["entry_atr_low"]  * atr14
    entry_high = close + p["entry_atr_high"] * atr14
    risk       = entry_low - (entry_low - p["stop_atr_mult"] * atr14)
    stop_loss  = entry_low - p["stop_atr_mult"] * atr14
    target     = entry_high + p["target_rr"] * risk
    return {
        "entry_low":  round(entry_low),
        "entry_high": round(entry_high),
        "stop_loss":  round(stop_loss),
        "target":     round(target),
        "hold_days":  p["hold_days"],
        "win_rate":   p["win_rate"],
        "pf":         p["profit_factor"],
    }


def calc_dip_levels(close, ma25, atr14):
    p = STRATEGY_PARAMS["dip"]
    entry_low  = ma25 * (1 + p["dev_lower"])
    entry_high = ma25 * (1 + p["dev_upper"])
    stop_loss  = entry_low - p["stop_atr_mult"] * atr14
    target     = entry_high * (1 + p["avg_return_10d"] * p["hold_days"])
    return {
        "entry_low":  round(entry_low),
        "entry_high": round(entry_high),
        "stop_loss":  round(stop_loss),
        "target":     round(target),
        "hold_days":  p["hold_days"],
        "win_rate":   p["win_rate"],
        "pf":         p["profit_factor"],
    }
