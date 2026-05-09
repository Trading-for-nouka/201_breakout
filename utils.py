import os
import requests

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")


def get_market_phase() -> str:
    """102_market_phase から市場フェーズを取得。失敗時は NEUTRAL。"""
    TOKEN = os.environ.get("PAT_TOKEN")
    url = "https://api.github.com/repos/trading-for-nouka/102_market_phase/contents/market_phase.json"
    headers = {
        "Authorization": f"token {TOKEN}" if TOKEN else "",
        "Accept": "application/vnd.github.v3.raw"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("phase", "NEUTRAL")
    except Exception as e:
        print(f"⚠️ フェーズ取得失敗（NETURALで継続）: {e}")
    return "NEUTRAL"


def send_discord(message: str) -> None:
    """Discord webhook 送信。失敗時はログのみ。"""
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"⚠️ Discord通知失敗: {e}")
