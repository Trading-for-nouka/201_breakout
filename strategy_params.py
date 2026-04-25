# バックテスト実績値に基づく戦略別パラメータ定数
# 更新日時      : 2026-04-26
# バックテスト  : 2016-01-01 〜 2025-12-31
# スコア(PF×勝率): 0.7969
# 勝率: 47.7% | PF: 1.67| 取引数: 79,473

STRATEGY_PARAMS = {

    # ============================================================
    # ブレイクアウト戦略（scan.py）
    # 実績: 勝率47.7% / PF1.67 / 保有21日
    # ============================================================
    "breakout": {
        "entry_atr_low":    0.0,
        "entry_atr_high":   0.3,
        "stop_atr_mult":    1.5,
        "target_rr":        2.0,
        "hold_days":        21,
        "win_rate":         0.477,
        "profit_factor":    1.67,
    },

    # ============================================================
    # 押し目買い戦略（scan_dip.py）
    # 実績: 勝率51.3% / PF1.55 / 保有15日
    # 最優秀パラメータ: DEV=-6〜+2% / RVOL≥0.8 / MA25
    # ============================================================
    "dip": {
        # エントリーゾーン（MA25乖離率ベース）
        "dev_lower":        -0.06,  # FIX: -0.05→-0.06（MA25の-6%）
        "dev_upper":        +0.02,  # FIX: +0.05→+0.02（MA25の+2%）

        # リスク管理
        "stop_atr_mult":    1.5,
        "hold_days":        15,     # FIX: 10→15

        # バックテスト実績
        "win_rate":         0.513,  # FIX: 0.535→0.513
        "profit_factor":    1.55,   # FIX: 1.25→1.55
        "avg_return_15d":   0.004,  # 15日平均リターン（推定値）
    },
}


def calc_breakout_levels(close, atr14):
    """
    ブレイクアウト戦略の定量売買水準を計算する。

    Args:
        close (float): 当日終値
        atr14 (float): 14日ATR

    Returns:
        dict: entry_low, entry_high, stop_loss, target
    """
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
    """
    押し目買い戦略の定量売買水準を計算する。

    Args:
        close (float): 当日終値
        ma25  (float): 25日移動平均
        atr14 (float): 14日ATR

    Returns:
        dict: entry_low, entry_high, stop_loss, target
    """
    p = STRATEGY_PARAMS["dip"]

    entry_low  = ma25 * (1 + p["dev_lower"])   # MA25 × 0.94
    entry_high = ma25 * (1 + p["dev_upper"])   # MA25 × 1.02
    stop_loss  = entry_low - p["stop_atr_mult"] * atr14
    target     = entry_high * (1 + p["avg_return_15d"] * p["hold_days"])

    return {
        "entry_low":  round(entry_low),
        "entry_high": round(entry_high),
        "stop_loss":  round(stop_loss),
        "target":     round(target),
        "hold_days":  p["hold_days"],
        "win_rate":   p["win_rate"],
        "pf":         p["profit_factor"],
    }
