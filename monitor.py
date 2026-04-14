import yfinance as yf
import json
import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- 【追加】会社名辞書作成関数 ---
def get_ticker_to_name():
    try:
        df_uni = pd.read_csv("universe230.csv", encoding='cp932')
        return dict(zip(df_uni['ticker'], df_uni['name']))
    except:
        return {}

# --- 決算またぎチェック関数 ---
def is_earnings_tomorrow(ticker):
    """明日が決算発表日かどうかを確認する"""
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is None or cal.empty:
            return False
        earnings_date = cal.iloc[0, 0]
        if hasattr(earnings_date, 'date'):
            earnings_date = earnings_date.date()
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        return earnings_date == tomorrow
    except:
        return False


# --- フェーズ取得関数 ---
def get_market_phase():
    OWNER = "trading-for-nouka"
    REPO = "102_market_phase"
    FILE_PATH = "market_phase.json"
    TOKEN = os.environ.get("PAT_TOKEN")
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}" if TOKEN else "", "Accept": "application/vnd.github.v3.raw"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("phase", "NEUTRAL")
    except: pass
    return "NEUTRAL"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
POS_FILE = "positions.json"

def send_discord(message):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": message})

def monitor():
    # 会社名辞書を読み込み
    ticker_to_name = get_ticker_to_name()
    
    phase = get_market_phase()
    if not os.path.exists(POS_FILE):
        print("ℹ️ positions.json が見つかりません。スキップします。")
        return

    try:
        with open(POS_FILE, "r", encoding="utf-8") as f:
            positions = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print("ℹ️ positions.json が空または不正です。スキップします。")
        return

    if not positions:
        print("ℹ️ 保有ポジションはありません。")
        return

    updated_positions = []
    exit_messages = []
    status_messages = []

    for p in positions:
        ticker = p["ticker"]
        name = ticker_to_name.get(ticker, p.get("name", "不明"))
        entry_price = p["entry_price"]
        entry_date = datetime.strptime(p["entry_date"], "%Y-%m-%d")
        days_held = (datetime.now() - entry_date).days
        
        df = yf.download(ticker, period="60d", progress=False, auto_adjust=True)
        if df.empty: continue
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        current_price = float(df["Close"].iloc[-1])
        high_price = float(df["High"].iloc[-1])
        low_price = float(df["Low"].iloc[-1])
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        closing_strength = (current_price - low_price) / (high_price - low_price) if (high_price - low_price) > 0 else 0
        df["atr"] = (df["High"] - df["Low"]).rolling(14).mean()
        atr = float(df["atr"].iloc[-1])

        atr_stop_price = entry_price - (atr * 1.5)
        
        df["ma25"] = df["Close"].rolling(25).mean()
        ma25 = float(df["ma25"].iloc[-1])
    
        has_profit_3pct = p.get("profit_exceeded_3pct", False)
        if profit_pct >= 3.0: has_profit_3pct = True
        p["profit_exceeded_3pct"] = has_profit_3pct

        
        # --- 決済判定 ---
        is_exit = False
        reason = ""

        if phase == "CRASH":
            is_exit, reason = True, "🛑 市場崩壊 (CRASH) 全決済"
        elif is_earnings_tomorrow(ticker):
            is_exit, reason = True, "📅 決算またぎ回避"
        elif profit_pct <= -5.0:
            is_exit, reason = True, "📉 強制損切り (-5%)"
            
        elif has_profit_3pct and profit_pct <= 0.5:
            is_exit, reason = True, "🛡️ 建値保護発動 (利益0.5%割れ)"
            
        elif current_price < atr_stop_price:
            is_exit, reason = True, "⚠️ ATR逆行ストップ"
            
        elif profit_pct > 0 and closing_strength <= 0.2:
            is_exit, reason = True, "💰 資金流出検知"
            
        elif current_price < ma25:
            is_exit, reason = True, "📉 トレンド終了 (25日線割れ)"
            
        elif days_held >= 21:
            is_exit, reason = True, "⏳ 期間満了 (21日経過)"
            
        if is_exit:
            exit_messages.append(f"🔥 **{ticker} {name}**: {reason} | 損益: {profit_pct:+.1f}%")
        else:
            p["name"] = name
            p["strategy"] = p.get("strategy", "breakout")
            if "stop_loss" not in p:
                p["stop_loss"] = round(entry_price * 0.95)
            updated_positions.append(p)
            status_messages.append(f"💰 {ticker} {name}: {profit_pct:+.1f}% ({days_held}日目)")

    with open(POS_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_positions, f, ensure_ascii=False, indent=2)

    jst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    if exit_messages or status_messages:
        msg = f"📉 **【{phase}】監視レポート**\n"
        if exit_messages: msg += "\n⚠️ **【決済推奨】**\n" + "\n".join(exit_messages)
        if status_messages: msg += "\n💰 **【保有中】**\n" + "\n".join(status_messages)
        msg += f"\n🕒 {jst.strftime('%Y/%m/%d %H:%M')} JST"
        send_discord(msg)

if __name__ == "__main__":
    monitor()
