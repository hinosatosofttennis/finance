# 必要なライブラリをインポート
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Flaskアプリケーションを作成
app = Flask(__name__)
# CORS(Cross-Origin Resource Sharing)を有効にし、ブラウザからのアクセスを許可
CORS(app)

# Renderのヘルスチェック用エンドポイント
@app.route('/')
def health_check():
    return jsonify({"status": "OK", "message": "Stock data server is running."})

def get_japanese_name(ticker_symbol):
    """
    Yahoo!ファイナンスのページをスクレイピングして日本語の銘柄名を取得する
    """
    try:
        url = f"https://finance.yahoo.co.jp/quote/{ticker_symbol}.T"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # YahooファイナンスのHTML構造変更に対応するため、複数の可能性を試す
        name_element = soup.select_one('h1[class*="_1fjd15b0"]')
        
        if name_element:
            return name_element.text.strip()
        return None
    except Exception as e:
        print(f"Could not scrape Japanese name for {ticker_symbol}: {e}")
        return None

def format_yen(value):
    """数値を億円・兆円単位の文字列にフォーマットする"""
    if value is None or not isinstance(value, (int, float)):
        return '---'
    if abs(value) >= 1000000000000:
        return f"{(value / 1000000000000):,.2f} 兆円"
    else:
        return f"{(value / 100000000):,.2f} 億円"

def get_stock_data(ticker_symbol):
    """
    証券コードを元に企業データを取得する関数
    """
    stock = yf.Ticker(f"{ticker_symbol}.T")
    info = stock.info
    
    # yfinanceでデータが取得できなかった場合の早期リターン
    if not info or info.get('regularMarketPrice') is None:
        raise Exception("yfinance APIから株価データを取得できませんでした")

    japanese_name = get_japanese_name(ticker_symbol)
    
    # 財務諸表の取得（エラーハンドリングを強化）
    try:
        income_stmt = stock.income_stmt
        if not income_stmt.empty:
            pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if 'Pretax Income' in income_stmt.index else None
            net_income = income_stmt.loc['Net Income'].iloc[0] if 'Net Income' in income_stmt.index else None
            latest_sales = income_stmt.loc['Total Revenue'].iloc[0] if 'Total Revenue' in income_stmt.index else None
        else:
            pretax_income, net_income, latest_sales = None, None, None
    except Exception:
        pretax_income, net_income, latest_sales = None, None, None
    
    raw_yield = info.get('dividendYield', 0) or 0
    formatted_yield = f"{(raw_yield * 100):.2f} %" if 0 < raw_yield < 1 else f"{raw_yield:.2f} %"

    data = {
        'companyName': japanese_name or info.get('longName', '---'),
        'code': ticker_symbol,
        'market': info.get('exchange', '---').replace('JPX', '東証'),
        'price': f"{info.get('currentPrice', 0):,}",
        'marketCap': format_yen(info.get('marketCap')),
        'pretaxIncome': format_yen(pretax_income),
        'netIncome': format_yen(net_income),
        'sales_latest': format_yen(latest_sales),
        'eps': info.get('trailingEps', '---'),
        'dividendYield': formatted_yield,
        'pbr': f"{info.get('priceToBook', 0):.2f}",
        'roe': f"{(info.get('returnOnEquity', 0) * 100):.2f} %",
        'bps': info.get('bookValue', '---'),
    }
    return data

@app.route('/stock-data')
def stock_data_endpoint():
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "証券コードが指定されていません"}), 400
    
    try:
        data = get_stock_data(code)
        return jsonify(data)
    except Exception as e:
        print(f"Error processing data for {code}: {e}")
        return jsonify({"error": f"データ処理失敗({code})", "code": code, "details": str(e)}), 500
