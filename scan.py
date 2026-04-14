import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import ta
import time
import json
from datetime import datetime, timedelta, timezone
from strategy_params import calc_breakout_levels
from claude_comment import generate_comments_batch

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
    except Exception as e:
        print(f"⚠️ フェーズ取得失敗: {e}")
    return "NEUTRAL"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
JSON_FILE = "selected_positions_breakout.json"

# --- 決算またぎチェック関数 ---
def is_near_earnings(ticker, days=5):
    """今後5日以内に決算発表がある場合はTrueを返す"""
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is None or cal.empty:
            return False
        earnings_date = cal.iloc[0, 0]
        if hasattr(earnings_date, 'date'):
            earnings_date = earnings_date.date()
        today    = datetime.now().date()
        deadline = today + timedelta(days=days)
        return today <= earnings_date <= deadline
    except:
        return False

# --- CSV読み込み ---
def load_universe(file_path="universe230.csv"):
    if not os.path.exists(file_path):
        print(f"❌ {file_path} が見つかりません。")
        return {}, {}

    df_uni = None
    for enc in ['cp932', 'utf-8-sig', 'utf-8']:
        try:
            df_uni = pd.read_csv(file_path, encoding=enc)
            print(f"✅ universe230.csv を {enc} で読み込みました。({len(df_uni)}行)")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"❌ {enc} での読み込みエラー: {e}")
            break

    if df_uni is None or df_uni.empty:
        print("❌ universe230.csv の読み込みに失敗しました。列名を確認してください。")
        return {}, {}

    required_cols = {'ticker', 'name', 'sector'}
    actual_cols = set(df_uni.columns.str.strip().str.lower())
    if not required_cols.issubset(actual_cols):
        print(f"❌ universe230.csv の列名が不正です。")
        print(f"   必要な列: {required_cols}")
        print(f"   実際の列: {set(df_uni.columns.tolist())}")
        return {}, {}

    df_uni.columns = df_uni.columns.str.strip()

    ticker_to_name = dict(zip(df_uni['ticker'], df_uni['name']))
    sector_dict = {}
    for _, row in df_uni.iterrows():
        s = row['sector']
        if s not in sector_dict: sector_dict[s] = {}
        sector_dict[s][row['ticker']] = row['name']
    return sector_dict, ticker_to_name

sector_stocks, ticker_to_name = load_universe()

# --- 各種補助関数 ---
def check_market():
    nikkei = yf.download("^N225", period="6mo", auto_adjust=True, progress=False)
    topix = yf.download("1306.T", period="6mo", auto_adjust=True, progress=False)
    def bullish(df):
        if df is None or df.empty or len(df) < 80: return False
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        close = df["Close"]
        ma25, ma75 = close.rolling(25).mean(), close.rolling(75).mean()
        return bool(close.iloc[-1] > ma25.iloc[-1] and ma25.iloc[-1] > ma75.iloc[-1])
    return bullish(nikkei) and bullish(topix)

def calculate_sector_strength():
    bench = yf.download("1306.T", period="10d", progress=False, auto_adjust=True)
    if bench.empty: return {s: 0 for s in sector_stocks.keys()}
    if isinstance(bench.columns, pd.MultiIndex): bench.columns = bench.columns.get_level_values(0)
    bench_5d_rev = float((bench['Close'].iloc[-1] / bench['Close'].iloc[-6]) - 1)
    sector_scores = {}
    for sector, stocks in sector_stocks.items():
        sector_returns = []
        for t in list(stocks.keys())[:3]:
            hist = yf.download(t, period="10d", progress=False, auto_adjust=True)
            if isinstance(hist.columns, pd.MultiIndex): hist.columns = hist.columns.get_level_values(0)
            if not hist.empty and len(hist) >= 6:
                sector_returns.append(float((hist['Close'].iloc[-1] / hist['Close'].iloc[-6]) - 1))
        if sector_returns:
            avg_ret = sum(sector_returns) / len(sector_returns)
            rel = avg_ret - bench_5d_rev
            sector_scores[sector] = 20 if rel > 0.02 else (10 if rel > 0 else 0)
        else: sector_scores[sector] = 0
    return sector_scores

def score_stock(ticker, sector, data, sector_strength, bench_return_20, bench_return_5, market_ok):
    if ticker not in data.columns.get_level_values(0):
        print(f"  ✗ {ticker} スキップ: データなし")
        return None
    df = data[ticker].copy().dropna()
    if len(df) < 250:
        print(f"  ✗ {ticker} スキップ: データ不足({len(df)}日分 < 250日)")
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df["ma25"] = df["Close"].rolling(25).mean()
    df["ma75"] = df["Close"].rolling(75).mean()
    df["vol_ma20"] = df["Volume"].rolling(20).mean()
    df["vol_ma5"] = df["Volume"].rolling(5).mean()
    df["high20"] = df["High"].rolling(20).max()
    df["high250"] = df["High"].rolling(250).max()
    latest = df.iloc[-1]
    l_close = float(latest["Close"])
    l_high = float(latest["High"])
    l_low = float(latest["Low"])
    ma25 = float(latest["ma25"])
    ma75 = float(latest["ma75"])
    rvol_today = float(latest["Volume"]) / latest["vol_ma20"] if latest["vol_ma20"] > 0 else 0
    rvol_short = latest["vol_ma5"] / latest["vol_ma20"] if latest["vol_ma20"] > 0 else 0
    stock_ret20 = df["Close"].pct_change(20).iloc[-1]
    if pd.isna(stock_ret20):
        return None
    relative_strength = stock_ret20 - bench_return_20
    if l_close < ma25:
        print(f"  ✗ {ticker} スキップ: MA25下")
        return None
    high10_prev = float(df["High"].rolling(10).max().iloc[-2])
    if l_close <= high10_prev:
        print(f"  ✗ {ticker} スキップ: 10日高値ブレイクアウト未達")
        return None
    if relative_strength <= 0:
        print(f"  ✗ {ticker} スキップ: RS負")
        return None
    high250_val = float(df["high250"].iloc[-1])
    if l_close < high250_val * 0.9:
        print(f"  ✗ {ticker} スキップ: 52週高値から10%超乖離")
        return None
    if latest["vol_ma20"] < 300000:
        print(f"  ✗ {ticker} スキップ: 流動性不足")
        return None
    if is_near_earnings(ticker):
        print(f"  ✗ {ticker} スキップ: 決算近接")
        return None
    score = 0
    reasons = []
    if ma25 > ma75:
        score += 20
        reasons.append(f"トレンド良好+20")
    if relative_strength > 0.05:
        score += 20
        reasons.append(f"RS強+20({relative_strength*100:.1f}%)")
    elif relative_strength > 0.02:
        score += 10
        reasons.append(f"RS並+10({relative_strength*100:.1f}%)")
    if rvol_today >= 1.5:
        score += 15
        reasons.append(f"出来高急増+15(RVOL:{rvol_today:.2f})")
    body_ratio = (l_close - l_low) / (l_high - l_low) if (l_high - l_low) > 0 else 0
    if body_ratio >= 0.8:
        score += 10
        reasons.append(f"引け強+10")
    sec_score = sector_strength.get(sector, 0)
    score += sec_score
    if sec_score > 0:
        reasons.append(f"セクター強+{sec_score}")
    if not market_ok:
        score -= 20
        reasons.append("市場不調-20")
    print(f"  ✔ {ticker}({ticker_to_name.get(ticker, '?')}) 合計:{score}点")
    atr14 = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
    levels = calc_breakout_levels(l_close, atr14)
    return {
        "ticker": ticker,
        "name": ticker_to_name.get(ticker, "Unknown"),
        "score": score,
        "close": round(l_close, 2),
        "price": round(l_close, 2),
        "sector": sector,
        "rvol": round(rvol_today, 2),
        "rs": round(relative_strength * 100, 2),
        "ma25": round(ma25, 2),
        "atr14": round(atr14, 2),
        "entry_low":  levels["entry_low"],
        "entry_high": levels["entry_high"],
        "stop_loss":  levels["stop_loss"],
        "target":     levels["target"],
        "hold_days":  levels["hold_days"],
    }

def send_discord(message):
    try: requests.post(DISCORD_WEBHOOK, json={"content": message})
    except: pass

def main():
    phase = get_market_phase()
    if phase in ["CRASH", "RISK_OFF"]:
        send_discord(f"🛑 **【{phase}モード】新規エントリー停止中**")
        return
    benchmark = yf.download("1306.T", period="3mo", auto_adjust=True, progress=False)
    if isinstance(benchmark.columns, pd.MultiIndex): benchmark.columns = benchmark.columns.get_level_values(0)
    bench_ret_20 = float(benchmark["Close"].pct_change(20).iloc[-1])
    bench_ret_5  = float(benchmark["Close"].pct_change(5).iloc[-1])
    market_ok = check_market()
    sector_strength = calculate_sector_strength()
    results = []
    tickers = []
    for sector, stocks in sector_stocks.items():
        tickers += list(stocks.keys())
    print(f"📥 データ取得中... {len(tickers)}銘柄")
    if not tickers:
        msg = "❌ universe230.csv から銘柄を読み込めませんでした。"
        print(msg)
        send_discord(msg)
        return
    data = yf.download(tickers, period="15mo", auto_adjust=True, progress=False, group_by="ticker")
    print(f"🚀 スキャン開始 (Phase: {phase})...")
    for sector, stocks in sector_stocks.items():
        for ticker in stocks.keys():
            try:
                res = score_stock(ticker, sector, data, sector_strength, bench_ret_20, bench_ret_5, market_ok)
                if res:
                    results.append(res)
            except Exception as e:
                print(f"❌ {ticker} スキャンエラー: {e}")
    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    if ranked:
        print("💬 Claude APIコメント生成中...")
        ranked = generate_comments_batch("breakout", ranked, max_count=5)
    if ranked:
        today_str = datetime.now().strftime("%Y-%m-%d")
        new_entries = []
        for r in ranked[:10]:
            new_entries.append({
                "ticker":        r["ticker"],
                "name":          r["name"],
                "entry_date":    today_str,
                "entry_price":   r["price"],
                "highest_price": r["price"],
                "stop_loss":     r["stop_loss"],
                "strategy":      "breakout",
            })
        existing = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, ValueError):
                existing = []
        existing_tickers = {p["ticker"] for p in existing}
        added = [e for e in new_entries if e["ticker"] not in existing_tickers]
        existing.extend(added)
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"💾 selected_positions_breakout.json に {len(added)} 件追記")
    jst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    p_icon = "🟢" if phase == "BULL" else "🧐"
    message = f"{p_icon} **【スキャン結果】({phase})**\n上位銘柄ランキング\n"
    if not ranked:
        message += "ℹ️ 該当する銘柄はありませんでした。"
        message += f"🕒 {jst.strftime('%Y/%m/%d %H:%M')} JST\n"
    else:
        for r in ranked[:10]:
            message += (f"✨ **{r['ticker']} {r['name']} ({r['score']}点)**\n"
                        f"┗ 価格: {r['price']}円 | RVOL: {r['rvol']} | RS: {r['rs']}%\n"
                        f"┗ 📌 購入: {r['entry_low']}〜{r['entry_high']}円 | 🛑 損切: {r['stop_loss']}円 | 🎯 目標: {r['target']}円\n")
            if r.get("comment"):
                message += f"┗ 💬 {r['comment']}\n"
            message += "\n"
        message += f"🕒 {jst.strftime('%Y/%m/%d %H:%M')} JST\n"
    send_discord(message)
    if results:
        log_df = pd.DataFrame(results)
        log_df.to_csv("scan_log.csv", index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    main()
