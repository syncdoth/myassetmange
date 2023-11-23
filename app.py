import os

from crypto_utils.my_crypto import main as mycrypto
from stock_utils.stock_prices import main as mystock
from send_discord import send_discord_message

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_daq as daq
import plotly.express as px
from dash.exceptions import PreventUpdate
import pandas as pd

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
sheet_id = os.environ.get("ASSET_GOOGLE_SHEET_ID")

app = Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "Sync.h Asset Portfolio"
server = app.server

app.layout = html.Div([
    html.H1("Asset Portfolio"),
    html.Hr(),
    html.Div(children=[
        html.P("Notify Telegram?", style={
            'display': 'inline-block',
            'margin-right': '10px'
        }),
        daq.BooleanSwitch(id='notify', on=True, style={'display': 'inline-block'}),
    ]),
    html.Br(),
    html.Button("Go!", id='go-button'),
    html.Hr(),
    dcc.Loading(
        id="loading-1",
        type="default",
        children=html.Div(id='output'),
    ),
],
                      style={'text-align': 'center'})


@app.callback(Output(component_id='output', component_property='children'),
              State(component_id='notify', component_property='on'),
              Input(component_id='go-button', component_property='n_clicks'))
def update_output_div(notify, n_clicks):
    if n_clicks is None:
        raise PreventUpdate

    rows = mycrypto(sheet_id=sheet_id, notify=False, return_data=True)
    data = {}
    for row in rows:
        if not row:
            continue
        float_ = lambda x: float(x.replace(",", "")) if x else x
        symbol, amount, krw_amount, usd_amount, _, usd_price = row
        amount = float_(amount)
        krw_amount = float_(krw_amount)
        usd_amount = float_(usd_amount)
        usd_price = float_(usd_price)
        data[symbol] = {
            "symbol": symbol,
            "amount": amount,
            "krw": krw_amount,
            "usd": usd_amount,
            "price": usd_price,
        }
    crypto_df = pd.DataFrame(data).T
    stock_df = mystock(sheet_id=sheet_id, return_data=True)

    crypto_df["class"] = "crypto"
    stock_df["class"] = "stock"

    total_stake = float(crypto_df.loc["TOTAL", "krw"] + stock_df.loc["TOTAL", "krw"])
    crypto_profit = float(crypto_df.loc["PROFIT", "krw"])
    stock_profit = float(stock_df.loc["PROFIT", "krw"])
    total_profit = crypto_profit + stock_profit

    totals_df = pd.DataFrame({
        "TOTAL": {
            "symbol": "TOTAL",
            "amount": "",
            "krw": total_stake,
            "usd": "",
            "price": "",
        },
        "PROFIT": {
            "symbol": "PROFIT",
            "amount": "",
            "krw": total_profit,
            "usd": "",
            "price": "",
        }
    }).T

    if notify:
        tao_price = crypto_df.loc["TAO", ["price"]].values[0]
        eth_price = crypto_df.loc["ETH", ["price"]].values[0]

        message = (f"TAO: ${tao_price:.2f} | ETH: ${eth_price:.2f}\n"
                   f"Crypto: ₩{crypto_profit:,.2f} | Stock: ₩{stock_profit:,.2f}\n"
                   f"Total Profit: ₩{total_profit:,.2f} | Total Asset: ₩{total_stake:,.2f}")
        send_discord_message(message)

    # prepare web
    padding = pd.DataFrame({c: [""] for c in crypto_df.columns})
    df = pd.concat([crypto_df, padding, stock_df, padding, totals_df])

    # set class to first column
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]

    portfolio = df[~df['symbol'].isin(["TOTAL", "PROFIT", "INVESTMENT"])]

    fig = px.pie(portfolio, values='usd', names='symbol', title='Portfolio')

    return [
        dash_table.DataTable(df.to_dict('records'), [{
            "name": i,
            "id": i
        } for i in df.columns]),
        dcc.Graph(figure=fig)
    ]


if __name__ == '__main__':
    app.run_server()
