from datetime import datetime
import unittest
import numpy

from capeval import Investor, CapeValidator


class TestInvestor(unittest.TestCase):

    def test_init(self):
        investor1 = Investor(15.)
        self.assertEqual(investor1.buy_at, 15.)
        self.assertEqual(investor1.sell_at, 15.)
        self.assertEqual(investor1.init_cash, 10000.)
        self.assertEqual(investor1.cash, 10000.)
        self.assertEqual(investor1.shares, 0.)
        self.assertEqual(investor1.income, 2000.)

        investor2 = Investor(16., 20., 5000., 22., 1000.)
        self.assertEqual(investor2.buy_at, 16.)
        self.assertEqual(investor2.sell_at, 20.)
        self.assertEqual(investor2.init_cash, 5000.)
        self.assertEqual(investor2.cash, 5000.)
        self.assertEqual(investor2.shares, 22.)
        self.assertEqual(investor2.income, 1000.)

    def test_get_paid(self):
        investor = Investor(18., init_cash=10., income=2.)
        for i in range(5):
            self.assertEqual(investor.cash, 10. + i * 2.)
            investor.get_paid()

    def test_get_net_worth(self):
        investor = Investor(18., init_cash=10., income=2., shares=0.)
        self.assertEqual(investor.get_net_worth(20.), 10.)
        investor.get_paid()
        self.assertEqual(investor.get_net_worth(20.), 12.)
        investor.shares = 5.
        self.assertEqual(investor.get_net_worth(20.), 112.)

    def test_sell_all(self):
        investor = Investor(18., init_cash=10., shares=0.)
        investor.sell_all(20.)
        self.assertEqual(investor.cash, investor.init_cash)
        self.assertEqual(investor.shares, 0.)
        investor.shares = 5.
        investor.sell_all(20.)
        self.assertEqual(investor.cash, 110.)
        self.assertEqual(investor.shares, 0.)

    def test_buy_all(self):
        investor = Investor(18., init_cash=100., shares=0., income=100.)
        investor.buy_all(20.)
        self.assertEqual(investor.shares, 5.)
        self.assertEqual(investor.cash, 0.)
        investor.get_paid()
        investor.buy_all(40.)
        self.assertEqual(investor.shares, 7.5)
        self.assertEqual(investor.cash, 0.)
        investor.buy_all(20.)
        self.assertEqual(investor.shares, 7.5)
        self.assertEqual(investor.cash, 0.)

    def test_react_to_pe(self):
        investor1 = Investor(18., init_cash=100., shares=0., income=100.)

        investor1.react_to_pe(20., 20.)  # don't buy
        self.assertEqual(investor1.shares, 0.)
        self.assertEqual(investor1.cash, 100.)

        investor1.react_to_pe(15., 20.)  # buy
        self.assertEqual(investor1.shares, 5.)
        self.assertEqual(investor1.cash, 0.)

        investor1.react_to_pe(15., 20.)  # hold (no cash)
        self.assertEqual(investor1.shares, 5.)
        self.assertEqual(investor1.cash, 0.)

        investor1.react_to_pe(20., 30.)  # sell
        self.assertEqual(investor1.shares, 0.)
        self.assertEqual(investor1.cash, 150.)

        investor1.get_paid()  # cash is now 250.
        investor1.react_to_pe(15., 10.)  # buy
        self.assertEqual(investor1.shares, 25.)
        self.assertEqual(investor1.cash, 0.)

        investor2 = Investor(18., sell_at=22., init_cash=100., shares=10.,
                             income=100.)

        investor2.react_to_pe(20., 20.)  # hold
        self.assertEqual(investor2.shares, 10.)
        self.assertEqual(investor2.cash, 100.)

        investor2.react_to_pe(23., 20.)  # sell
        self.assertEqual(investor2.shares, 0.)
        self.assertEqual(investor2.cash, 300.)

        investor2.react_to_pe(19., 20.)  # hold
        self.assertEqual(investor2.shares, 0.)
        self.assertEqual(investor2.cash, 300.)

        investor2.react_to_pe(15., 30.)  # buy
        self.assertEqual(investor2.shares, 10.)
        self.assertEqual(investor2.cash, 0.)


class TestCapeValidator(unittest.TestCase):
    def setUp(self):
        data_file = 'pe_data.csv'
        start_date = datetime(2011, 8, 1)
        end_date = datetime(2011, 11, 15)
        self.buys = [25., 21., 20.1, 19.8, 19.]
        self.validator = CapeValidator(
            data_file, start_date, self.buys, end_date=end_date)

    def test_init(self):
        expected_dates = [
            datetime(2011, 8, 1),
            datetime(2011, 9, 1),
            datetime(2011, 10, 3),
            datetime(2011, 11, 1)
        ]
        self.assertEqual([pe[0] for pe in self.validator.pe_array],
                         expected_dates)
        expected_pe = [22.6, 20.04, 19.69, 20.15]
        self.assertEqual([pe[1] for pe in self.validator.pe_array],
                         expected_pe)

        self.assertEqual(len(self.validator.investors), 5)
        for buy, investor in zip(self.buys, self.validator.investors):
            self.assertEqual(investor.buy_at, buy)
            self.assertEqual(investor.cash, 10000.)
            self.assertEqual(investor.income, 2000.)
            self.assertEqual(investor.sell_at, buy)
            self.assertEqual(investor.shares, 0.)

    def assertVectorAlmostEqual(self, v1, v2, places=3, **kwargs):
        index = 0
        for val1, val2 in zip(v1, v2):
            msg = 'Index {}'.format(index)
            self.assertAlmostEqual(val1, val2, places=places, msg=msg,
                                   **kwargs)
            index += 1

    def test_worth_calculation(self):
        self.validator.calculate_worth_vs_time()
        prices = {
            datetime(2011, 8, 1): 1286.94,
            datetime(2011, 9, 1): 1204.42,
            datetime(2011, 10, 3): 1099.23,
            datetime(2011, 11, 1): 1218.28
        }
        for key, val in prices.items():
            self.assertEqual(self.validator.index_cache[key], val)

        c0 = 12000.
        inc = 2000.

        # investor1 always buys
        expected_share = numpy.array([
            c0 / 1286.94,
            c0 / 1286.94 + inc / 1204.42,
            c0 / 1286.94 + inc / 1204.42 + inc / 1099.23,
            c0 / 1286.94 + inc / 1204.42 + inc / 1099.23 + inc / 1218.28
        ])
        expected_worth = numpy.array([
            c0,
            inc + 1204.42 * expected_share[0],
            inc + 1099.23 * expected_share[1],
            inc + 1218.28 * expected_share[2]
        ])
        self.assertVectorAlmostEqual(
            self.validator.shares_matrix[0], expected_share)
        self.assertVectorAlmostEqual(
            self.validator.cash_matrix[0], numpy.zeros(4))
        self.assertVectorAlmostEqual(
            self.validator.worth_matrix[0], expected_worth)

        # investor 2 goes hold, buy, buy, buy
        expected_share = numpy.array([
            0.,
            (c0 + inc) / 1204.42,
            (c0 + inc) / 1204.42 + inc / 1099.23,
            (c0 + inc) / 1204.42 + inc / 1099.23 + inc / 1218.28,
        ])
        expected_cash = numpy.array([c0, 0., 0., 0.])
        expected_worth = numpy.array([
            c0,
            inc + c0,
            inc + 1099.23 * expected_share[1],
            inc + 1218.28 * expected_share[2]
        ])
        self.assertVectorAlmostEqual(
            self.validator.shares_matrix[1], expected_share)
        self.assertVectorAlmostEqual(
            self.validator.cash_matrix[1], expected_cash)
        self.assertVectorAlmostEqual(
            self.validator.worth_matrix[1], expected_worth)

        # investor 3 goes hold, buy, buy, sell
        expected_share = numpy.array([
            0.,
            (c0 + inc) / 1204.42,
            (c0 + inc) / 1204.42 + inc / 1099.23,
            0.,
        ])
        expected_cash = numpy.array([
            c0, 0., 0., inc + 1218.28 * expected_share[2]])
        expected_worth = numpy.array([
            c0,
            inc + c0,
            inc + 1099.23 * expected_share[1],
            inc + 1218.28 * expected_share[2]
        ])
        self.assertVectorAlmostEqual(
            self.validator.shares_matrix[2], expected_share)
        self.assertVectorAlmostEqual(
            self.validator.cash_matrix[2], expected_cash)
        self.assertVectorAlmostEqual(
            self.validator.worth_matrix[2], expected_worth)

        # investor 4 goes hold, hold, buy, sell
        expected_share = numpy.array([
            0.,
            0.,
            (c0 + 2 * inc) / 1099.23,
            0.,
        ])
        expected_cash = numpy.array([
            c0, c0 + inc, 0., inc + 1218.28 * expected_share[2]])
        expected_worth = numpy.array([
            c0,
            c0 + inc,
            c0 + 2 * inc,
            inc + 1218.28 * expected_share[2]
        ])
        self.assertVectorAlmostEqual(
            self.validator.shares_matrix[3], expected_share)
        self.assertVectorAlmostEqual(
            self.validator.cash_matrix[3], expected_cash)
        self.assertVectorAlmostEqual(
            self.validator.worth_matrix[3], expected_worth)

        # investor 5 always holds
        expected_worth = c0 + 2000. * numpy.arange(0, 5, 1)
        self.assertVectorAlmostEqual(
            self.validator.shares_matrix[4], numpy.zeros(4))
        self.assertVectorAlmostEqual(
            self.validator.cash_matrix[4], expected_worth)
        self.assertVectorAlmostEqual(
            self.validator.worth_matrix[4], expected_worth)


if __name__ == '__main__':
    unittest.main()
