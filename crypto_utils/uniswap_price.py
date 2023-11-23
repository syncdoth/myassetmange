from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from itertools import permutations
from uniswap import Uniswap
from web3 import Web3

PROVIDER = "https://mainnet.infura.io/v3/da307c1e384c419f85d3c8c732e4cfd6"


class Token:

    def __init__(self, address, symbol, decimals) -> None:
        self.address = Web3.to_checksum_address(address)
        self._raw_address = address
        self.symbol = symbol
        self.decimals = decimals
        self.qty = 10**self.decimals


class UniswapPrice:
    sides = {'sell': 'get_price_output', 'buy': 'get_price_input'}

    percentages = [50, 100]
    fees = [100, 300, 3000, 10000]

    def __init__(self, v2, v3):
        self.swap = {
            'v2': {
                'exchange': v2,
                'percentages': self.percentages,
                'fees': [3000]
            },
            'v3': {
                'exchange': v3,
                'percentages': self.percentages,
                'fees': self.fees
            }
        }

    def find_best(self):
        prices = [perm[0] + perm[1] for perm in permutations(self.pool_prices('different'), 2)
                 ] + self.pool_prices('single')
        if len(prices) == 0:
            return
        if self.side == 'sell':
            return min(prices)
        elif self.side == 'buy':
            return max(prices)

    def get_price(self, exchange, fee, qty):
        queue = [self.t0.address, self.t1.address
                ] if self.side == 'buy' else [self.t1.address, self.t0.address]
        price_func = getattr(exchange, self.sides[self.side])
        return price_func(*queue, qty, fee=fee) / self.t1.qty

    def pool_prices(self, price_type):
        if price_type == 'single':
            perc = 100
        elif price_type == 'different':
            perc = 50

        return [
            fee[perc]
            for exchanges in self.futures.values()
            for fee in exchanges.values()
            if isinstance(fee[perc], float)
        ]

    def get_best_price(self, t0, t1, side):
        self.t0 = t0
        self.t1 = t1
        self.side = side

        self.get_prices()
        return self.find_best()

    def get_prices(self):
        self.futures = defaultdict(dict)

        with ThreadPoolExecutor(max_workers=10) as executor:
            for exchange_name, exchange_data in self.swap.items():
                self.futures[exchange_name] = defaultdict(dict)
                for fee in exchange_data['fees']:
                    self.futures[exchange_name][fee] = defaultdict(dict)
                    for percentage in exchange_data['percentages']:
                        self.futures[exchange_name][fee][percentage] = defaultdict(dict)
                        qty = self.t0.qty * percentage // 100
                        self.futures[exchange_name][fee][percentage] = executor.submit(
                            self.get_price, exchange_data['exchange'], fee, qty)

            for exchange_name, exchange_fees in self.futures.items():
                self.futures[exchange_name] = dict(exchange_fees)
                for fee, percentage_data in exchange_fees.items():
                    self.futures[exchange_name][fee] = dict(percentage_data)
                    for percentage, future in percentage_data.items():
                        try:
                            self.futures[exchange_name][fee][percentage] = future.result()
                        except:
                            pass


def get_price_calculator():
    web3 = Web3(Web3.HTTPProvider(PROVIDER))

    uni_v2 = Uniswap(address=None, private_key=None, version=2, web3=web3)

    uni_v3 = Uniswap(address=None, private_key=None, version=3, web3=web3)

    price_calculator = UniswapPrice(uni_v2, uni_v3)

    def _price_calculator_api(token1, token2):
        t1 = Token(token1['address'], token1['symbol'], token1['decimals'])
        t2 = Token(token2['address'], token2['symbol'], token2['decimals'])
        price = price_calculator.get_best_price(t1, t2, "sell")
        if price is None:
            price = price_calculator.get_best_price(t1, t2, "buy")
            if price is None:
                print(f"can't fetch price for this pair ({token1['symbol']}-{token2['symbol']})")
            return 0
        return price

    return _price_calculator_api
