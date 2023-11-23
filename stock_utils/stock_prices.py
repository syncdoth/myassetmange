import os
import json
import sys
import requests

from bs4 import BeautifulSoup
import pandas as pd
from wallstreet import Stock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fiat_exchange import FiatEx
from google_sheet import open_sheet


def get_kr_stock_price(company_ticker_symbol, lookback=1):
    url_form = "https://fchart.stock.naver.com/sise.nhn?symbol={company_ticker_symbol}&timeframe=day&count={lookback}&requestType=0"
    url = url_form.format(company_ticker_symbol=company_ticker_symbol, lookback=lookback)

    response = requests.get(url)
    bs_obj = BeautifulSoup(response.content, "html.parser")
    bs_res = bs_obj.select('item')
    informations = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = pd.DataFrame([], columns=informations, index=range(len(bs_res)))

    for i in range(len(bs_res)):
        df.iloc[i] = str(bs_res[i]['data']).split('|')

    df['Date'] = pd.to_datetime(df['Date'])
    return float(df.iloc[-1]['Close'])


def get_us_stock_price(ticker):
    info = Stock(ticker)
    return info.price


def open_assets(path):
    with open(path, 'r') as f:
        assets = json.load(f)
    return assets


def main(sheet_id=None, return_data=False):
    if sheet_id is None:
        sheet_id = os.environ.get("ASSET_GOOGLE_SHEET_ID", None)
        if sheet_id is None:
            raise ValueError("sheet_id is not provided")
    pd.options.display.float_format = '{:,.2f}'.format
    forex = FiatEx()

    usd2krw = forex.get_fiat_fx("USD", "KRW")

    assets = open_sheet(sheet_id)
    assets = assets[assets["CLASS"] == "stock"]
    investment_krw = assets[assets["SUBTYPE"] == "inv"]["AMOUNT"]

    data = {}
    for i, row in assets.iterrows():
        asset = row["ASSET"]
        amount = row["AMOUNT"]
        if row["SUBTYPE"] == "inv":
            continue
        if row["SUBTYPE"] == "kr":
            ticker = row["TICKER"].replace("\"", "")
            try:
                krw_price = get_kr_stock_price(ticker)
                data[asset] = {
                    "amount": amount,
                    "krw": amount * krw_price,
                    "usd": "",
                    "price": krw_price,
                }
            except:
                print(f'Failed to get {asset} ({ticker}) price')
                data[asset] = {"amount": amount, "krw": 0, "usd": 0, "price": 0}

        elif row["SUBTYPE"] == "us":
            try:
                usd_price = get_us_stock_price(asset)
                usd_amount = amount * usd_price
                data[asset] = {
                    "amount": amount,
                    "krw": usd_amount * usd2krw,
                    "usd": usd_amount,
                    "price": usd_price,
                }
            except:
                print(f'Failed to get {asset} price')
                data[asset] = {"amount": amount, "krw": 0, "usd": 0, "price": 0}
    df = pd.DataFrame(data)
    df['TOTAL'] = ["", df.loc["krw"].sum(), "", ""]
    df["INVESTMENT"] = ["", investment_krw, 0, ""]
    df['PROFIT'] = ["", df['TOTAL']['krw'] - investment_krw, "", ""]
    df = df.T
    df['symbol'] = df.index
    # set symbol to first column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]

    if return_data:
        return df
    else:
        print(df.drop(columns=['symbol']))


if __name__ == '__main__':
    main()
