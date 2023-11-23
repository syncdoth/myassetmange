import os
import datetime
import glob
import io
import requests
import zipfile

import pandas as pd

BASEPATH = os.path.dirname(os.path.abspath(__file__))


class FiatEx:
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip?a6ef9319d740f54c034942a0317114f8"

    def __init__(self, force_download=False) -> None:
        self.filepath = self.download(force_download=force_download)
        self.rate = pd.read_csv(self.filepath).iloc[0]  # take most recent

    def download(self, force_download=False):

        def _download(url, fpath):
            print("ecb data may be stale. Downloading fresh data...")
            response = requests.get(url)
            z = zipfile.ZipFile(io.BytesIO(response.content))
            z.extractall()

            csv_file = z.namelist()[0]
            z.extract(csv_file)

            # Rename the file to your desired filepath
            os.rename(csv_file, fpath)

        filepath = f"ecb-{datetime.datetime.today().strftime('%Y-%m-%d')}.csv"
        filepath = os.path.join(BASEPATH, filepath)
        if (not os.path.exists(filepath) or
                os.path.getmtime(filepath) < datetime.datetime.now().timestamp() - 86400 or
                force_download):
            _download(self.url, filepath)
            # delete stale files
            stale_files = glob.glob(os.path.join(BASEPATH, "ecb-*.csv"))
            for f in stale_files:
                if f != filepath:
                    os.remove(f)

        return filepath

    def get_fiat_fx(self, fiat1, fiat2):
        return self.rate[fiat2] / self.rate[fiat1]
