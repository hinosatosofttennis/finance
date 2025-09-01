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

def get_japanese_name(ticker_symbol):
    """
    Yahoo!ファイナンスのページをスクレイピングして日本語の銘柄名を取得する
    """
    try:
        url = f"https://finance.yahoo.co.jp/quote/{ticker_symbol}.T"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        
        soup = BeautifulSoup(response.content, 'html.parser')
        # h1タグの中から銘柄名が含まれる要素を特定してテキストを取得
        name_element = soup.select_one('h1[class*="_1fjd15b0"]')
        
        if name_element:
            return name_element.text.strip()
        return None
    except Exception as e:
        print(f"Failed to scrape Japanese name for {ticker_symbol}: {e}")
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
    
    # ★★★ 日本語の銘柄名を取得 ★★★
    japanese_name = get_japanese_name(ticker_symbol)
    
    income_stmt = stock.income_stmt
    pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if not income_stmt.empty and 'Pretax Income' in income_stmt.index else None
    net_income = income_stmt.loc['Net Income'].iloc[0] if not income_stmt.empty and 'Net Income' in income_stmt.index else None
    latest_sales = income_stmt.loc['Total Revenue'].iloc[0] if not income_stmt.empty and 'Total Revenue' in income_stmt.index else None
    
    raw_yield = info.get('dividendYield', 0) or 0
    formatted_yield = f"{(raw_yield * 100):.2f} %" if 0 < raw_yield < 1 else f"{raw_yield:.2f} %"

    data = {
        # ★★★ 取得した日本語名を使用。失敗した場合はyfinanceの英語名を使う ★★★
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
        return jsonify({"error": f"データ処理失敗({code})", "code": code}), 500
