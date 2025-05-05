from flask import Flask, request, jsonify
import requests
import pandas as pd
import os

app = Flask(__name__)  # ← 這行很重要！Flask 物件初始化

def fetch_ohlcv(symbol, interval):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=500'
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_asset_volume','num_trades',
        'taker_buy_base','taker_buy_quote','ignore'
    ])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    return df[['open_time', 'open', 'high', 'low', 'close']]

def calculate_indicators(df):
    df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD_Line'] = df['EMA12'] - df['EMA26']
    df['Signal_Line'] = df['MACD_Line'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD_Line'] - df['Signal_Line']

    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['prev_close'] = df['close'].shift(1)
    df['high_low'] = df['high'] - df['low']
    df['high_pc'] = abs(df['high'] - df['prev_close'])
    df['low_pc'] = abs(df['low'] - df['prev_close'])
    df['TR'] = df[['high_low','high_pc','low_pc']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    df['Signal'] = df['MACD_Hist'].apply(lambda x: '多頭' if x > 0 else '空頭')
    return df

@app.route('/analyze')
def analyze():
    symbol = request.args.get('symbol', 'BTCUSDT')
    interval = request.args.get('interval', '15m')
    df = fetch_ohlcv(symbol, interval)
    df = calculate_indicators(df)
    df = df.iloc[-100:]

    result = {
        'time': df['open_time'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
        'open': df['open'].tolist(),
        'high': df['high'].tolist(),
        'low': df['low'].tolist(),
        'close': df['close'].tolist(),
        'macd': df['MACD_Line'].round(4).tolist(),
        'signal': df['Signal_Line'].round(4).tolist(),
        'hist': df['MACD_Hist'].round(4).tolist(),
        'rsi': df['RSI'].round(2).tolist(),
        'atr': df['ATR'].round(4).tolist(),
        'suggestion': df['Signal'].tolist()
    }
    return jsonify(result)

@app.route('/')
def index():
    return "Crypto Technical Analysis API"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
