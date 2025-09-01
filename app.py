# 必要なライブラリをインポート
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd

# Flaskアプリケーションを作成
app = Flask(__name__)
# CORS(Cross-Origin Resource Sharing)を有効にし、ブラウザからのアクセスを許可
CORS(app)

def format_yen(value):
    """数値を億円・兆円単位の文字列にフォーマットする"""
    if value is None or not isinstance(value, (int, float)):
        return '---'
    if abs(value) >= 1000000000000: # 1兆以上
        return f"{(value / 1000000000000):,.2f} 兆円"
    else: # 億円
        return f"{(value / 100000000):,.2f} 億円"

def get_stock_data(ticker_symbol):
    """
    証券コードを元に企業データを取得する関数
    """
    stock = yf.Ticker(f"{ticker_symbol}.T")
    info = stock.info
    
    # 損益計算書を取得
    income_stmt = stock.income_stmt
    
    # 最新の税引前利益と当期利益を取得
    pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if not income_stmt.empty and 'Pretax Income' in income_stmt.index else None
    net_income = income_stmt.loc['Net Income'].iloc[0] if not income_stmt.empty and 'Net Income' in income_stmt.index else None
    latest_sales = income_stmt.loc['Total Revenue'].iloc[0] if not income_stmt.empty and 'Total Revenue' in income_stmt.index else None
    
    raw_yield = info.get('dividendYield', 0) or 0
    formatted_yield = f"{(raw_yield * 100):.2f} %" if 0 < raw_yield < 1 else f"{raw_yield:.2f} %"

    data = {
        'companyName': info.get('longName', '---'),
        'code': ticker_symbol,
        'market': info.get('exchange', '---').replace('JPX', '東証'),
        'price': f"{info.get('currentPrice', 0):,}",
        
        # 追加項目
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
    """
    '/stock-data?code=xxxx' のURLでアクセスされた時に動作するエンドポイント
    """
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "証券コードが指定されていません"}), 400
    
    try:
        data = get_stock_data(code)
        return jsonify(data)
    except Exception as e:
        print(f"Error fetching data for {code}: {e}")
        return jsonify({"error": f"データ取得失敗({code})", "code": code}), 500
