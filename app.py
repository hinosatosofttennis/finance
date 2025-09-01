# ファイル名: app.py

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

def get_japanese_name(ticker_symbol_with_suffix):
    """
    Yahoo!ファイナンスのページをスクレイピングして日本語の銘柄名を取得する
    """
    try:
        url = f"https://finance.yahoo.co.jp/quote/{ticker_symbol_with_suffix}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        name_element = soup.select_one('h1[class*="_1fjd15b0"]')
        
        if name_element:
            return name_element.text.strip()
        return None
    except Exception as e:
        print(f"Could not scrape Japanese name for {ticker_symbol_with_suffix}: {e}")
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
    # ★★★ ここから修正箇所 ★★★
    # 検索対象とする市場の識別子リスト (優先順位順)
    exchanges = ['.T', '.F', '.S', '.N'] 
    stock_info = None
    stock_obj = None
    successful_ticker = None

    for suffix in exchanges:
        try:
            ticker_with_suffix = f"{ticker_symbol}{suffix}"
            temp_stock = yf.Ticker(ticker_with_suffix)
            temp_info = temp_stock.info
            
            # データが有効かどうかのチェック
            if temp_info and temp_info.get('regularMarketPrice') is not None:
                stock_info = temp_info
                stock_obj = temp_stock
                successful_ticker = ticker_with_suffix
                print(f"Found data for {successful_ticker}")
                break # データが見つかったのでループを抜ける
        except Exception:
            continue # エラーが出たら次の市場を試す

    # どの市場でもデータが見つからなかった場合
    if not stock_info:
        raise Exception(f"対応市場（東証, 福証, 札証, 名証）で株価情報が見つかりませんでした")
    # ★★★ 修正ここまで ★★★

    japanese_name = get_japanese_name(successful_ticker)
    
    try:
        income_stmt = stock_obj.income_stmt
        if not income_stmt.empty:
            pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if 'Pretax Income' in income_stmt.index else None
            net_income = income_stmt.loc['Net Income'].iloc[0] if 'Net Income' in income_stmt.index else None
            latest_sales = income_stmt.loc['Total Revenue'].iloc[0] if 'Total Revenue' in income_stmt.index else None
        else:
            pretax_income, net_income, latest_sales = None, None, None
    except Exception:
        pretax_income, net_income, latest_sales = None, None, None
    
    raw_yield = stock_info.get('dividendYield', 0) or 0
    formatted_yield = f"{(raw_yield * 100):.2f} %" if 0 < raw_yield < 1 else f"{raw_yield:.2f} %"

    data = {
        'companyName': japanese_name or stock_info.get('longName', '---'),
        'code': ticker_symbol,
        'market': stock_info.get('exchange', '---').replace('JPX', '東証').replace('FSE', '福証'),
        'price': f"{stock_info.get('currentPrice', 0):,}",
        'marketCap': format_yen(stock_info.get('marketCap')),
        'pretaxIncome': format_yen(pretax_income),
        'netIncome': format_yen(net_income),
        'sales_latest': format_yen(latest_sales),
        'eps': stock_info.get('trailingEps', '---'),
        'dividendYield': formatted_yield,
        'pbr': f"{stock_info.get('priceToBook', 0):.2f}",
        'roe': f"{(stock_info.get('returnOnEquity', 0) * 100):.2f} %",
        'bps': stock_info.get('bookValue', '---'),
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
        return jsonify({"error": str(e), "code": code}), 500
