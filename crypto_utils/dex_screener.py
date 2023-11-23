import requests

API_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"


def get_token_price(address):
    url = API_URL.format(address)
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()

    prices = {}
    for x in data["pairs"]:
        quote = x["quoteToken"]["symbol"]
        native_price = x["priceNative"]
        usd_price = x["priceUsd"]
        prices[quote] = {"native": float(native_price), "usd": float(usd_price)}
    return prices
