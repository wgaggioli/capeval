import argparse
import os
import pickle
from datetime import datetime, timedelta
from matplotlib.dates import YearLocator, DateFormatter, MonthLocator

import numpy
from matplotlib import pyplot as plt
from pandas.io.data import get_data_yahoo


class Investor(object):
    """Represents a single investor with initial cash, income, and
    set buy/sell thresholds.

    :param buy_at   float   if the pe ratio is less than or equal to this
      value, the investor will buy all the shares she can
    :param sell_at  float   if the pe ratio is greater than this value, the
      investor will sell all her shares (if any)
    :param init_cash float  initial cash
    :param shares   float   initial shares
    :param income   float   cash increase on call to `get_paid`

    """
    def __init__(self, buy_at, sell_at=None, init_cash=10000., shares=0.,
                 income=2000.):
        self.buy_at = buy_at
        if sell_at is None:
            sell_at = buy_at
        self.sell_at = sell_at
        self.init_cash = self.cash = init_cash
        self.shares = shares
        self.income = income

    def get_paid(self):
        """Receive the income"""
        self.cash += self.income

    def get_net_worth(self, market_price):
        """Total net worth is cash + worth of shares"""
        return self.cash + self.shares * market_price

    def sell_all(self, market_price):
        """Convert all stocks to cash"""
        self.cash += market_price * self.shares
        self.shares = 0.

    def buy_all(self, market_price):
        """Buy all shares I can afford"""
        self.shares += self.cash / market_price
        self.cash = 0.

    def react_to_pe(self, pe_ratio, market_price):
        """React to P/E depending on investor thresholds (buy, sell, or hold)

        """
        if self.shares and pe_ratio > self.sell_at:
            self.sell_all(market_price)
        elif self.cash and pe_ratio <= self.buy_at:
            self.buy_all(market_price)


class CapeValidator(object):
    """
    Compares the performance of a suite of investors with different buy/sell
    thresholds for CAPE ratio.

    :param pe_data_file str csv of pe_data. TODO: write script to download
    :param start_date   datetime    datetime at which to start analysis
    :param buy_thresholds   [float, ...]    list of buy thresholds for suite
        of investors. Each entry will instantiate a new investor.
    :param sell_thresholds [float, ...]     list of sell thresholds
        corresponding to `buy_thresholds`. If None, will be equal to
        `buy_thresholds`.
    :param end_date datetime    datetime at which to stop analysis. If None,
        will go to current day.
    :param index    str     stock symbol of index to invest in.

    """
    def __init__(self, pe_data_file, start_date, buy_thresholds,
                 sell_thresholds=None, end_date=None, index='^GSPC'):
        if sell_thresholds is None:
            sell_thresholds = [None] * len(buy_thresholds)
        if len(buy_thresholds) != len(sell_thresholds):
            raise RuntimeError("Buy and Sell Thresholds must be equal length")
        if end_date is None:
            end_date = datetime.now()
        self.investors = []
        self.pe_array = []
        self.index = index
        self.index_cache = {}

        self.load_pe_array(pe_data_file, start_date, end_date)
        self.init_investors(buy_thresholds, sell_thresholds)
        self.load_index_cache()
        size = (len(self.investors), len(self.pe_array))
        self.worth_matrix = numpy.empty(size)
        self.shares_matrix = numpy.empty(size)
        self.cash_matrix = numpy.empty(size)

    @property
    def _cache_filename(self):
        return '.cache_{}.pkl'.format(self.index)

    def _parse_pe_date(self, date_str):
        # the date_str is the beginning of the month, but we want the end
        # because the CAPE for a given month is the avg of prices for the
        # entire month
        date0 = datetime.strptime(date_str, '%m/%Y')
        date = date0 + timedelta(27)
        while date.month == date0.month or date.weekday() > 4:
            date += timedelta(1)
        return date

    def load_pe_array(self, pe_data_file, start_date, end_date):
        """Load the CAPE data from the specified file"""
        with open(pe_data_file) as fp:
            for line in fp:
                line = line.strip()
                if line:
                    date_str, pe = line.split(',')
                    pe = float(pe)
                    date = self._parse_pe_date(date_str)
                    if start_date <= date <= end_date:
                        self.pe_array.append([date, pe])

    def init_investors(self, buy_thresholds, sell_thresholds):
        """Initialize Investor instances from threshold lists"""
        for b, s in zip(buy_thresholds, sell_thresholds):
            self.investors.append(Investor(b, s))

    def load_index_cache(self):
        """Load the cache for the specified index, if available"""
        if os.path.exists(self._cache_filename):
            with open(self._cache_filename, 'rb') as fp:
                self.index_cache = pickle.load(fp)

    def save_index_cache(self):
        """Save the cache to disk"""
        with open(self._cache_filename, 'wb') as fp:
            pickle.dump(self.index_cache, fp)

    def _get_market_price(self, date, try_next=2):
        """Get the market price for the given date from yahoo or the cache.

        Tries to account for holidays by stepping backwards through time when
        the specified date is not found. Intermittent network errors may cause
        unexpected results here.

        """
        while date.weekday() > 4:
            date -= timedelta(1)
        if date in self.index_cache:
            return self.index_cache[date]
        try:
            df = get_data_yahoo(self.index, date, date)
            price = df['Adj Close'][0]
        except (IndexError, OSError):
            # try to account for holidays and wutnot
            if try_next:
                date1 = date - timedelta(1)
                return self._get_market_price(date1, try_next - 1)
            else:  # pragma no cover
                raise
        self.index_cache[date] = price
        return price

    def calculate_worth_vs_time(self):
        """Calculate the worth, shares, and cash of all the investors across
        the specified time interval

        """
        i = 0
        for date, pe_ratio in self.pe_array:
            market_price = self._get_market_price(date)
            for j, investor in enumerate(self.investors):
                investor.get_paid()
                investor.react_to_pe(pe_ratio, market_price)
                self.worth_matrix[j][i] = investor.get_net_worth(market_price)
                self.shares_matrix[j][i] = investor.shares
                self.cash_matrix[j][i] = investor.cash
            i += 1
        self.save_index_cache()

    def plot_worth_vs_time(self, names=None):
        """Plot the worth of each investor vs. time. If names is specified,
        will use these names in the legend. Otherwise, will name the investors
        based off their thresholds.

        """
        if names is None:
            names = [
                'Investor ({:0.2f},{:0.2f})'.format(inv.buy_at, inv.sell_at)
                for inv in self.investors]
        dates = [x[0] for x in self.pe_array]
        year = YearLocator()
        date_fmt = DateFormatter('%Y')
        plt.xkcd()

        # investor worth plots
        fig = plt.figure()
        ax = fig.gca()
        lines = []
        for i in range(len(self.investors)):
            result = ax.plot_date(dates, self.worth_matrix[i], '-')
            lines.append(result[0])
        ax.xaxis.set_major_locator(year)
        ax.xaxis.set_major_formatter(date_fmt)
        # ax.xaxis.set_minor_formatter(MonthLocator())
        ax.autoscale_view()
        ax.legend(lines, names, 'upper left')
        fig.autofmt_xdate()
        return fig

    def plot_pe_ratio(self):
        dates = [x[0] for x in self.pe_array]
        year = YearLocator()
        date_fmt = DateFormatter('%Y')

        fig = plt.figure()
        ax_pe = fig.gca()
        ax_pe.plot_date(dates, [x[1] for x in self.pe_array], '-')
        ax_pe.xaxis.set_major_locator(year)
        ax_pe.xaxis.set_major_formatter(date_fmt)
        ax_pe.autoscale_view()
        ax_pe.set_title('PE Ratio vs. Time')
        fig.autofmt_xdate()
        return fig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAPE Value determination")
    default_thresholds = ','.join(str(i) for i in range(16, 26)) + ',1000'
    parser.add_argument('-t', '--buy_thresholds',  default=default_thresholds)
    parser.add_argument('--sell_thresholds', default=None)
    parser.add_argument('--pe_file', default='pe_data.csv')
    parser.add_argument('--index', default='^GSPC')
    parser.add_argument('--start_date', default='01/1980')
    parser.add_argument('--end_date', default=None)
    args = parser.parse_args()

    buys = [float(b) for b in args.buy_thresholds.split(',')]
    sells = args.sell_thresholds
    if sells:
        sells = [float(b) for b in sells.split(',')]
    d0 = datetime.strptime(args.start_date, '%m/%Y')
    if args.end_date:
        d1 = datetime.strptime(args.end_date, '%m/%Y')
    else:
        d1 = datetime.now()

    validator = CapeValidator(args.pe_file, d0, buys, sells, d1, args.index)
    validator.calculate_worth_vs_time()
    import ipdb; ipdb.set_trace()
    validator.plot_worth_vs_time()
    # validator.plot_pe_ratio()
    plt.show()
