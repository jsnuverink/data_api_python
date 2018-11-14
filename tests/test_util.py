import unittest

from data_api import util
import datetime

import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.ERROR)


class ClientTest(unittest.TestCase):

    def test_check_reachability_server(self):

        # Usually google should be reachable
        self.assertTrue(util.check_reachability_server("https://www.google.com"))
        self.assertFalse(util.check_reachability_server("https://www.google-nonexisting.com"))

    def test_convert_date(self):

        # Check if correct timezone information is attached
        date = util.convert_date("2017-12-15 15:05:43.258077+01:00")  # have offset as set
        self.assertEqual(date.utcoffset(), datetime.timedelta(hours=1))
        date = util.convert_date("2016-07-29 14:01")  # need to have +2 offset (summer time)
        self.assertEqual(date.utcoffset(), datetime.timedelta(hours=2))
        date = util.convert_date("2018-11-14 11:17:38.362582")  # need to have +1 offset (winter time)
        self.assertEqual(date.utcoffset(), datetime.timedelta(hours=1))


if __name__ == '__main__':
    unittest.main()
