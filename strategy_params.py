# バックテスト実績値に基づく戦略別パラメータ定数
# 更新日時      : 2026-04-26
# バックテスト  : 2016-01-01 〜 2025-12-31
# スコア(PF×勝率): 0.7945
# 勝率: 47.7% | PF: 1.67 | 取引数: 4,972

STRATEGY_PARAMS = {

    # ============================================================
    # ブレイクアウト戦略（scan.py）
    # 実績: 勝率47.7% / PF1.67 / 保有21日
    # 最優秀パラメータ: 7日高値ブレイク / MA20>MA50 / RS+3%以上 / RVOL≥2.0
    # ============================================================
    "breakout": {
        # エントリーゾーン（ATRベース）
        "entry_atr_low":    0.0,    # 終値そのまま（即エントリー下限）
        "entry_atr_high":   0.3,    # 終値 + 0.3×ATR（翌日寄り付き許容上限）

        # リスク管理
        "stop_atr_mult":    1.5,    # 損切り: エントリー下限 - 1.5×ATR
        "target_rr":        2.0,    # 利確: リスクの2倍（RR=2.0）

        # 保有期間
        "hold_days":        21,

        # バックテスト実績
        "win_rate":         0.477,
        "profit_factor":    1.67,
    },
}


def calc_breakout_levels(close, atr14):
    """
    ブレイクアウト戦略の定量売買水準を計算する。

    Args:
        close (float): 当日終値
        atr14 (float): 14日ATR

    Returns:
        dict: entry_low, entry_high, stop_loss, target, hold_days
    """
    p = STRATEGY_PARAMS["breakout"]

    entry_low  = close + p["entry_atr_low"]  * atr14   # = close
    entry_high = close + p["entry_atr_high"] * atr14   # = close + 0.3×ATR

    risk      = p["stop_atr_mult"] * atr14
    stop_loss = entry_low - risk
    target    = entry_high + p["target_rr"] * risk

    return {
        "entry_low":  round(entry_low),
        "entry_high": round(entry_high),
        "stop_loss":  round(stop_loss),
        "target":     round(target),
        "hold_days":  p["hold_days"],
        "win_rate":   p["win_rate"],
        "pf":         p["profit_factor"],
    }
