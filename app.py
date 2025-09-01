# 必要なライブラリをインポート
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random

# Flaskアプリケーションを作成
app = Flask(__name__)
# CORS(Cross-Origin Resource Sharing)を有効にし、ブラウザからのアクセスを許可
CORS(app)

# Renderのヘルスチェック用エンドポイント
@app.route('/')
def health_check():
    return jsonify({"status": "OK", "message": "Stock data server is running."})

def get_japanese_name_from_yahoo_jp(ticker_with_suffix):
    """
    Yahoo!ファイナンスから日本語の銘柄名を取得する
    """
    try:
        url = f"https://finance.yahoo.co.jp/quote/{ticker_with_suffix}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        }
        time.sleep(random.uniform(0.5, 1.5))
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        selectors = ['h1[class*="_1fjd15b0"]', 'h1[class*="symbol"]', 'h1']
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if any('\u3040' <= char <= '\u9FAF' for char in text):
                    suffix_to_remove = "の株価・株式情報"
                    if text.endswith(suffix_to_remove):
                        return text[:-len(suffix_to_remove)].strip()
                    return text
                    
    except Exception as e:
        print(f"Scraping failed for {ticker_with_suffix}: {e}")
    
    return None

def format_yen(value):
    """数値を億円・兆円単位の文字列にフォーマットする"""
    if not isinstance(value, (int, float)): return '---'
    if abs(value) >= 1000000000000: return f"{(value / 1000000000000):,.2f} 兆円"
    return f"{(value / 100000000):,.2f} 億円"

def get_stock_data(ticker_symbol):
    """
    証券コードを元に企業データを取得する関数
    """
    exchanges = ['.T', '.F', '.S', '.N']
    stock_info, stock_obj, successful_ticker = None, None, None

    for suffix in exchanges:
        try:
            ticker_with_suffix = f"{ticker_symbol}{suffix}"
            temp_stock = yf.Ticker(ticker_with_suffix)
            temp_info = temp_stock.info
            
            if temp_info and temp_info.get('regularMarketPrice') is not None:
                stock_info, stock_obj, successful_ticker = temp_info, temp_stock, ticker_with_suffix
                break
        except Exception:
            continue

    if not stock_info:
        raise Exception("対応市場で株価情報が見つかりませんでした")

    japanese_name = get_japanese_name_from_yahoo_jp(successful_ticker)
    
    try:
        income_stmt = stock_obj.income_stmt
        pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if not income_stmt.empty and 'Pretax Income' in income_stmt.index else None
        net_income = income_stmt.loc['Net Income'].iloc[0] if not income_stmt.empty and 'Net Income' in income_stmt.index else None
        latest_sales = income_stmt.loc['Total Revenue'].iloc[0] if not income_stmt.empty and 'Total Revenue' in income_stmt.index else None
    except Exception:
        pretax_income, net_income, latest_sales = None, None, None
    
    raw_yield = stock_info.get('dividendYield', 0) or 0
    formatted_yield = f"{(raw_yield * 100):.2f} %" if 0 < raw_yield < 1 else f"{raw_yield:.2f} %"

    data = {
        'companyName': japanese_name or stock_info.get('longName', '---'),
        'code': ticker_symbol,
        'market': stock_info.get('exchange', '').replace('JPX', '東証').replace('FSE', '福証').replace('SSE', '札証').replace('NAG', '名証'),
        'price': f"{stock_info.get('currentPrice', 0):,}",
        # --- ★★★ ここから追加箇所 ★★★ ---
        'change': stock_info.get('regularMarketChange', 0),
        'changePercent': stock_info.get('regularMarketChangePercent', 0) * 100,
        # --- ★★★ 追加ここまで ★★★ ---
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
        return jsonify({"error": str(e), "code": code}), 500
