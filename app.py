# ファイル名: app.py
# 機能: フロントエンドからのリクエストに応じて、Yahoo!ファイナンスから株価データを取得し、返す役割。

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
        if financials.empty:
            latest_sales = 'N/A'
        else:
            # 最新の総売上高(Total Revenue)を取得し、億円単位に変換
            latest_sales = f"{(financials.loc['Total Revenue'].iloc[0] / 100000000):.2f} 億円"
    except (KeyError, IndexError):
        latest_sales = 'N/A'
        
    # データを整理して辞書型オブジェクトに格納
    # info.get(key, '---') は、データが存在しない場合に'---'を返すための記述
    data = {
        'companyName': info.get('longName', '---'),
        'code': ticker_symbol,
        'market': info.get('exchange', '---').replace('JPX', '東証'),
        'price': f"{info.get('currentPrice', 0):,}", # 3桁区切り
        
        # 業績
        'sales_latest': latest_sales,
        # APIの仕様上、「今期予想」の売上・経常利益を直接取得するのは困難です
        'operatingIncome_forecast': '---', 
        
        # 各種指標
        'eps': info.get('trailingEps', '---'),
        'dividendYield': f"{(info.get('dividendYield', 0) * 100):.2f} %",
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
    # URLのパラメータから証券コードを取得
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "証券コードが指定されていません"}), 400
    
    try:
        # データを取得
        data = get_stock_data(code)
        # JSON形式でデータを返す
        return jsonify(data)
    except Exception as e:
        print(f"Error fetching data for {code}: {e}")
        return jsonify({"error": "データの取得に失敗しました。証券コードが正しいか確認してください。"}), 500

# このファイルが直接実行された場合にサーバーを起動
if __name__ == '__main__':
    # ポート番号5000でサーバーを起動
    app.run(host='0.0.0.0', port=5000)
