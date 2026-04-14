import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

def get_data(tickers, days_back=200):
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    # 複数銘柄を一括ダウンロード（通信回数を最小化）
    data = yf.download(tickers, start=start_date, interval="1d", group_by='ticker', threads=True)
    return data

def calculate_indicators(df):
    # MA
    df['MA25'] = df['Close'].rolling(window=25).mean()
    df['MA75'] = df['Close'].rolling(window=75).mean()
    
    # ATR (True Rangeの簡略版)
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    return df
