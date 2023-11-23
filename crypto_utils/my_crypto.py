import os
import re
import sys

import pandas as pd
from mexc_sdk import Spot
from rich.console import Console, Text
from rich.table import Table
from termcolor import colored
import fire

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from send_discord import send_discord_message
from uniswap_price import get_price_calculator
from dex_screener import get_token_price
from fiat_exchange import FiatEx
from google_sheet import open_sheet


class CryptoEx:

    def __init__(self, asset_info) -> None:
        self.mexc = Spot(api_key=os.environ["MEXC_API_KEY"], api_secret=os.environ["MEXC_SECRET"])

        # Some token addresses we'll be using later in this guide
        self.address_book = asset_info[["ASSET", "ADDRESS",
                                        "DECIMALS"]].set_index("ASSET").to_dict(orient="index")

    def get_crypto_fx(self, symbol1, symbol2):
        if symbol1 in ("ETH", "WETH"):
            return float(self.mexc.avg_price(symbol1 + symbol2)["price"])
        token1 = self.address_book.get(symbol1, None)
        token2 = self.address_book.get(symbol2, None)

        prices = get_token_price(token1["ADDRESS"])
        if prices is None:
            print(f"Can't fetch coin price for {symbol1} using dexscreener. Trying UniSwap...")
        elif symbol2 in ("USDT", "USDC", "DAI"):
            return max(p['usd'] for p in prices.values())
        elif symbol2 == "ETH":
            return prices["WETH"]["native"]
        elif symbol2 in prices:
            return prices[symbol2]["native"]

        if token1 is None or token2 is None:
            print(f"symbol1: {symbol1} or symbol2: {symbol2} is not implemented. Returning 0")
            return 0
        token1["symbol"] = symbol1
        token2["symbol"] = symbol2
        price = get_price_calculator()(token1, token2)
        if isinstance(price, dict):
            price = price["avg"]
        return price


def format_number(n, c=3, d=2):
    if c == 3:
        return f"{n:,.{d}f}"
    return re.sub(rf"(\d)(?=(\d{{{c}}})+(?!\d))", r"\1,", f"{n:.{d}f}")


def cprint(s, color=None):
    print(colored(s, color))


def main(sheet_id=None, notify=False, return_data=False):
    if sheet_id is None:
        sheet_id = os.environ.get("ASSET_GOOGLE_SHEET_ID", None)
        if sheet_id is None:
            raise ValueError("sheet_id is not provided")
    asset_info = open_sheet(sheet_id)
    asset_info = asset_info[asset_info["CLASS"] == "crypto"]
    total_inv_krw = float(asset_info[asset_info["SUBTYPE"] == "inv"]["AMOUNT"])
    asset_info = asset_info[asset_info["SUBTYPE"] == "dex"]

    forex = FiatEx()
    cex = CryptoEx(asset_info)

    usd2krw = forex.get_fiat_fx("USD", "KRW")
    eth_price = cex.get_crypto_fx("ETH", "USDT")

    table = Table(show_footer=True, width=None, pad_edge=False, box=None, expand=True)
    table.add_column(
        "[underline white]TYPE",
        footer_style="overline white",
        style="bold white",
    )
    table.add_column(
        "[underline white]Amount",
        style="rgb(50,163,219)",
        no_wrap=True,
        justify="left",
    )
    table.add_column(
        "[underline white]KRW",
        style="rgb(50,163,219)",
        no_wrap=True,
        justify="left",
    )
    table.add_column(
        "[underline white]USD",
        style="rgb(50,163,219)",
        no_wrap=True,
        justify="left",
    )
    table.add_column(
        "[underline white]ETH",
        style="rgb(50,163,219)",
        no_wrap=True,
        justify="left",
    )
    table.add_column(
        "[underline white]PRICE (USD)",
        style="rgb(50,163,219)",
        no_wrap=True,
        justify="left",
    )

    table.add_row(
        "INVESTMENT",
        "",
        format_number(total_inv_krw, 4, 0),
        "",
        "",
        "",
        style="magenta",
    )
    table.add_row()
    # cprint(f"total investment: {format_number(asset_info['total_inv']['krw'], 4, 0)} KRW", 'cyan')
    # cprint("\nAssets:", 'magenta')

    total_asset_usd = 0
    tao_price = None

    rows = []
    # for asset_class, info in asset_info["asset"].items():
    for i, row in asset_info.iterrows():
        symbol = row["ASSET"]
        amount = row["AMOUNT"]
        eth_amount = None
        if amount == 0:
            continue
        if not "USD" in symbol:
            price = cex.get_crypto_fx(symbol, "USDT")
            if price == 0:
                price = cex.get_crypto_fx(symbol, "WETH")
                price = price * eth_price
            usd_amount = amount * price

            price_in_eth = (cex.get_crypto_fx(symbol, "ETH") if symbol != "ETH" else 1)
            eth_amount = amount * price_in_eth
            if symbol == "TAO":
                tao_price = price
        else:
            price = 1
            usd_amount = amount
        total_asset_usd += usd_amount

        # cprint(
        #     f"- {symbol}: {format_number(amount, 3, 6)} | {format_number(usd_amount, 3, 2)} USD | {format_number(usd_amount * usd2krw, 4, 0)} KRW",
        #     'blue')
        rows.append([
            symbol,
            format_number(amount, 3, 4),
            format_number(usd_amount * usd2krw, 4, 0),
            format_number(usd_amount, 3, 2),
            format_number(eth_amount, 3, 6) if eth_amount else "",
            format_number(price, 3, 6)
        ])

    total_asset_krw = total_asset_usd * usd2krw
    total_profit_krw = total_asset_krw - total_inv_krw
    pos = total_profit_krw >= 0
    plusminus = "+" if pos else ""

    rows.append([
        "TOTAL", "",
        format_number(total_asset_krw, 4, 0),
        format_number(total_asset_usd, 3, 2), "", ""
    ])
    rows.append([])
    rows.append(["PROFIT", "", plusminus + format_number(total_profit_krw, 4, 0), "", "", ""])

    console = Console()
    for i, row in enumerate(rows):
        if i == len(rows) - 1:
            style = "green" if pos else "red"
        else:
            style = None
        table.add_row(*row, style=style)

    # cprint(
    #     f"Total: {format_number(total_asset_usd, 3, 2)} USD | {format_number(total_asset_krw, 4, 0)} KRW",
    #     'yellow')
    # cprint(f"\nProfit: {plusminus}{format_number(total_profit_krw, 4, 0)} KRW",
    #        'green' if pos else 'red')
    if notify:
        # notify using discord
        message = []
        message.append(
            f"Current Profit = {plusminus + '₩' + format_number(total_profit_krw, 4, 0)}")
        message.append(f"$TAO = {tao_price:.4f} | $ETH = {eth_price:.4f}")
        message = '\n'.join(message)
        send_discord_message(message)

        # apple OSscript for notification
        # call_notify(
        #     "Current Profit",
        #     f"{plusminus + format_number(total_profit_krw, 4, 0)} | $TAO = {tao_price:.4f}")
    if return_data:
        return rows
    else:
        console.print(table)
        cprint(f"1 USD = {usd2krw:.4f} KRW", "yellow")


def call_notify(title, text):
    os.system("""osascript -e 'display notification "{}" with title "{}"'""".format(text, title))


if __name__ == "__main__":
    fire.Fire(main)
