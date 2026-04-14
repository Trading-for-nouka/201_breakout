# claude_comment.py
# Claude APIを使って銘柄コメントを生成するモジュール
# scan.py / scan_dip.py から呼び出す

import os
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-haiku-4-5-20251001"   # コスト重視。品質向上時はsonnet-4-6に変更

# ============================================================
# システムプロンプト（共通）
# ============================================================
SYSTEM_PROMPT = """
あなたは日本株トレードのアシスタントです。
スキャン結果データをもとに、個人トレーダー向けの簡潔なコメントを日本語で生成してください。

【出力形式】必ず以下の3行構成で出力すること。余計な前置きは不要。
1行目: 選出理由（1文、なぜこの銘柄が候補なのか）
2行目: 📌 購入検討: {entry_low}〜{entry_high}円 / 🛑 損切り: {stop_loss}円 / 🎯 利確目標: {target}円（保有{hold_days}日目安）
3行目: ⚠️ 注意点（1文、過熱感・決算・市場環境など）

数値は必ずデータの値をそのまま使うこと。自分で計算しないこと。
""".strip()


def _build_user_prompt(strategy, signal):
    """戦略に応じたユーザープロンプトを生成する"""

    base = f"""
戦略: {strategy}
銘柄: {signal['ticker']} {signal['name']}
終値: {signal['close']}円
ATR14: {signal['atr14']}円
MA25: {signal.get('ma25', 'N/A')}円
RVOL: {signal['rvol']}倍
RS(対TOPIX): {signal.get('rs', 'N/A')}%
乖離率(対MA25): {signal.get('dev', 'N/A')}%

【定量売買水準（Pythonで計算済み）】
購入検討ゾーン: {signal['entry_low']}〜{signal['entry_high']}円
損切りライン:   {signal['stop_loss']}円
利確目標:       {signal['target']}円
保有期間目安:   {signal['hold_days']}日

【バックテスト実績（2015-2025）】
""".strip()

    if strategy == "breakout":
        base += f"""
戦略概要: 10日高値ブレイクアウト・出来高急増・RSフィルター通過
勝率: 53% / PF: 1.25 / 平均保有: 21日
"""
    elif strategy == "dip":
        base += f"""
戦略概要: MA25近辺への押し目・反発確認・RSフィルター通過
勝率: 53.5% / PF: 1.25 / 平均保有: 10日 / 平均リターン: +0.427%
"""

    base += "\n銘柄の直近ニュース・決算・材料をweb検索で確認してから、上記の形式でコメントを生成してください。"
    return base


def generate_comment(strategy, signal):
    """
    Claude APIを呼び出してコメントを生成する。

    Args:
        strategy (str): "breakout" or "dip"
        signal   (dict): スキャン結果 + 定量売買水準を含む辞書

    Returns:
        str: 生成されたコメント。失敗時はNone。
    """
    if not ANTHROPIC_API_KEY:
        print("⚠️ ANTHROPIC_API_KEY が設定されていません。コメント生成をスキップします。")
        return None

    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    payload = {
        "model":      MODEL,
        "max_tokens": 1000,
        "system":     SYSTEM_PROMPT,
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search"
            }
        ],
        "messages": [
            {
                "role":    "user",
                "content": _build_user_prompt(strategy, signal)
            }
        ],
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        texts = [
            block["text"]
            for block in data["content"]
            if block.get("type") == "text"
        ]
        return "\n".join(texts).strip()

    except requests.exceptions.Timeout:
        print(f"⚠️ Claude API タイムアウト ({signal['ticker']})")
        return None
    except Exception as e:
        print(f"⚠️ Claude API エラー ({signal['ticker']}): {e}")
        return None


def generate_comments_batch(strategy, signals, max_count=5):
    """
    複数銘柄のコメントをまとめて生成する（上位N件のみ）。

    Args:
        strategy  (str):  "breakout" or "dip"
        signals   (list): signal辞書のリスト
        max_count (int):  コメント生成する最大件数（コスト節約）

    Returns:
        list: signal辞書に "comment" キーを追加したリスト
    """
    results = []
    for i, sig in enumerate(signals):
        if i < max_count:
            print(f"  💬 コメント生成中: {sig['ticker']} {sig['name']} ({i+1}/{min(len(signals), max_count)})")
            comment = generate_comment(strategy, sig)
            sig["comment"] = comment if comment else "（コメント生成失敗）"
        else:
            sig["comment"] = None
        results.append(sig)
    return results
