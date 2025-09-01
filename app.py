# ファイル名: app.py

# 必要なライブラリをインポート
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd

# Flaskアプリケーションを作成
app = Flask(__name__)
# CORS(Cross-Origin Resource Sharing)を有効にし、ブラウザからのアクセスを許可
CORS(app)

def get_stock_data(ticker_symbol):
    """
    証券コードを元に企業データを取得する関数
    """
    # 日本株の証券コードには末尾に ".T" を付ける
    stock = yf.Ticker(f"{ticker_symbol}.T")
    
    # 企業情報を取得
    info = stock.info
    
    # 財務諸表を取得（データがない場合のエラーを考慮）
    try:
        financials = stock.financials
        if financials.empty or 'Total Revenue' not in financials.index:
            latest_sales = '---'
        else:
            # 最新の総売上高(Total Revenue)を取得し、億円単位に変換
            latest_sales = f"{(financials.loc['Total Revenue'].iloc[0] / 100000000):,.2f} 億円"
    except Exception:
        latest_sales = '---'

    # --- ここから配当利回りの修正 ---
    raw_yield = info.get('dividendYield', 0) or 0 # Noneの場合も0として扱う

    # 取得した値が1より大きいか小さいかで処理を分岐
    if raw_yield > 1:
        # 既にパーセント形式の場合 (例: 3.5)
        formatted_yield = f"{raw_yield:.2f} %"
    else:
        # 小数形式の場合 (例: 0.035)
        formatted_yield = f"{(raw_yield * 100):.2f} %"
    # --- 修正ここまで ---

    # データを整理して辞書型オブジェクトに格納
    data = {
        'companyName': info.get('longName', '---'),
        'code': ticker_symbol,
        'market': info.get('exchange', '---').replace('JPX', '東証'),
        'price': f"{info.get('currentPrice', 0):,}", # 3桁区切り
        
        # 業績
        'sales_latest': latest_sales,
        'operatingIncome_forecast': '---', # yfinanceでは予想値の取得は困難
        
        # 各種指標
        'eps': info.get('trailingEps', '---'),
        'dividendYield': formatted_yield, # 修正した変数を使用
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
    except Exception:
        return jsonify({"error": "データの取得に失敗しました。証券コードが正しいか確認してください。"}), 500
