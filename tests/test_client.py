import unittest

import math

import datetime
import data_api as api
from data_api import Aggregation

import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.ERROR)


class ClientTest(unittest.TestCase):


    def test_retrieve(self):  # Only works if the testserver.py server is running
        now = datetime.datetime.now()
        end = now
        start = end - datetime.timedelta(minutes=10)

        data = api.get_data(channels=["A", "B"], start=start, end=end,
                            base_url="http://localhost:8080/archivertestdata")
        print(data)

        # Test function returns 10 datapoints with values from 0 to 9
        self.assertEqual(data.shape[0], 10)

        for i in range(10):
            self.assertEqual(data["A"][i], i)

        print(data["A"])

    def test_retrieve_merge(self):  # Only works if the testserver.py server is running
        now = datetime.datetime.now()
        end = now
        start = end - datetime.timedelta(minutes=10)

        data = api.get_data(channels=["A", "B"], start=start, end=end,
                            base_url="http://localhost:8080/archivertestdatamerge")
        print(data)

        # Test function returns 10 datapoints with values from 0 to 9
        self.assertEqual(data.shape[0], 20)

        counter = 0
        for i in range(20):
            if i % 2 == 0:
                self.assertEqual(data["A"][i], counter)
                counter += 1
            else:
                self.assertTrue(math.isnan(data["A"][i]))

        print(data["A"])

    def test_real_aggregation(self):
        now = datetime.datetime.now() - datetime.timedelta(hours=10)
        data = api.get_data(["SINDI01-RIQM-DCP10:FOR-PHASE-AVG", "S10CB01-RBOC-DCP10:FOR-PHASE-AVG"],
                            start=now, delta_range=100, index_field="pulseId", aggregation=Aggregation(nr_of_bins=100))

        self.assertEqual(data.shape[0], 100)
        print(data)

    def test_real(self):  # Only works if archiver is accessible and data is available for used channel
        # Retrieve data from the archiver

        now = datetime.datetime.now()
        end = now - datetime.timedelta(minutes=1)
        start = end - datetime.timedelta(hours=12)

        data = api.get_data(channels=['sf-archiverappliance/S10CB02-CVME-ILK:CENTRAL-CORETEMP',
                                      'sf-archiverappliance/S10CB02-CVME-ILK:CENTRAL-CORETEMP2'], start=start, end=end)

        print(data)
        self.assertTrue(True)

    def test_real_raw(self):  # Only works if archiver is accessible and data is available for used channel
        # Retrieve data from the archiver

        now = datetime.datetime.now()
        end = now - datetime.timedelta(minutes=1)
        start = end - datetime.timedelta(minutes=1)

        data = api.get_data(channels=[
                                      # 'sf-archiverappliance/S10CB02-CVME-ILK:CENTRAL-CORETEMP',
                                      # 'sf-archiverappliance/S10CB02-CVME-ILK:CENTRAL-CORETEMP2',
                                      'sf-databuffer/S10CB01-RKLY-DCP10:FOR-AMPLT-MAX',
                                      'sf-databuffer/S10CB01-RKLY-DCP10:REF-AMPLT-MAX',
                                      # 'sf-archiverappliance/S10CB01-CVME-ILK:P2020-CORETEMP'
                                     ],
                            start=start, end=end, mapping_function=lambda d, **kwargs: d,
                            server_side_mapping=True,
                            server_side_mapping_strategy="fill-null"
                            )

        print(data)
        self.assertTrue(True)

    def test_real_search(self):
        channels = api.search("FOR-PHASE-AVG")
        print(channels)
        self.assertTrue(True)

    def test_real_get_supported_backends(self):
        backends = api.get_supported_backends()
        print(backends)
        self.assertTrue(True)

    def test_get_global_date(self):
        dates = api.get_global_date(4253312491)
        print(dates)
        dates = api.get_global_date([4253312291, 4253312391, 4253312491, 4253312591])
        print(dates)
        self.assertTrue(True)

    def test_get_data_iread(self):
        now = datetime.datetime.now()
        end = now - datetime.timedelta(minutes=1)
        start = end - datetime.timedelta(minutes=1)

        data = api.get_data_iread(channels=[
            'sf-databuffer/SINEG01-RCIR-PUP10:SIG-AMPLT-MAX',
        ],
            start=start, end=end, filename='test.h5')

        print(data)

        pass

    def test_parse_duration(self):

        # Month and year durations are not supported!
        raised = False
        try:
            api.parse_duration("P2Y")
        except RuntimeError:
            raised = True

        self.assertTrue(raised)

        # Check correct parsing
        delta = api.parse_duration("PT1H")
        self.assertEqual(delta, datetime.timedelta(hours=1))

        delta = api.parse_duration("PT1H70M")
        self.assertEqual(delta, datetime.timedelta(hours=1, minutes=70))

        print(delta)


if __name__ == '__main__':
    unittest.main()
