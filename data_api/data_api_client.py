from datetime import datetime, timedelta
import requests
import os
import pandas as pd
import json


def _convert_date(date_string):
    """
    Convert a date string in isoformat
    
    Parameters
    ----------
    date_string : string
        Date string in ("%Y-%m-%d %H:%M" or "%Y-%m-%d %H:%M:%S") format
    
    Returns
    -------
    st : 
        isoformat version of the string
    """
    try:
        st = datetime.strptime(date_string, "%Y-%m-%d %H:%M")
    except:
        try:
            st = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        except:
            print("[ERROR]")
    return st, datetime.isoformat(st)


def _set_pulseid_range(start_pulseid, end_pulseid, delta):
    d = {}
    if start_pulseid == 0 and end_pulseid == 0:
        raise RuntimeError("Must select at least start_pulseid or end_pulseid")
    if start_pulseid != 0:
        d["startPulseId"] = start_pulseid
        if end_pulseid != 0:
            d["endPulseId"] = end_pulseid
        else:
            d["endPulseId"] = start_pulseid + delta
    else:
        d["endPulseId"] = end_pulseid
        d["startPulseId"] = end_pulseid - delta

    return d


def _set_time_range(start_date, end_date, delta_time):
    d = {}
    if start_date == "" and end_date == "":
        d["startDate"] = datetime.isoformat(datetime.now() - timedelta(seconds=delta_time))
        d["endDate"] = datetime.isoformat(datetime.now())
    else:
        if start_date != "" and end_date != "":
            st_dt, st_iso = _convert_date(start_date)
            d["startDate"] = st_iso
            st_dt, st_iso = _convert_date(end_date)
            d["endDate"] = st_iso
        elif start_date != "":
            st_dt, st_iso = _convert_date(start_date)
            d["startDate"] = st_iso
            d["endDate"] = datetime.isoformat(st_dt + timedelta(seconds=delta_time))
        else:
            st_dt, st_iso = _convert_date(end_date)
            d["endDate"] = st_iso
            d["startDate"] = datetime.isoformat(st_dt - timedelta(seconds=delta_time))
    return d


def configure(source_name="http://data-api.psi.ch/", ):
    """
    Factory method to create a DataApiClient instance.
    
    Parameters
    ----------
    source_name : string
        Name of the Data source. Can be a Data API server, or a JSON file dumped from a Data API server
    
    Returns
    -------
    dac : 
        DataApiClient instance
    """
    return DataApiClient(source_name=source_name)


class DataApiClient(object):

    source_name = None
    is_local = False
    _aggregation = {}
    
    def __init__(self, source_name="http://data-api.psi.ch/"):
        self.source_name = source_name
        if os.path.isfile(source_name):
            self.is_local = True

    def set_aggregation(self, aggregation_type="value", aggregations=["min", "mean", "max"], extrema=[],
                        nr_of_bins=None, duration_per_bin=None, pulses_per_bin=None):
        print("[WARNING] Server-wise aggregation still not fully supported")
        
        # keep state?
        self._aggregation["aggregationType"] = aggregation_type
        self._aggregation["aggregations"] = aggregations
        if extrema != []:
            self._aggregation["extrema"] = []
        if (nr_of_bins is not None) + (duration_per_bin is not None) + (pulses_per_bin is not None) > 1:
            print("[ERROR] must specify only one of nr_of_bins, duration_per_bin or pulse_per_bin")
            return
        
        if nr_of_bins is not None:
            self._aggregation["nrOfBins"] = nr_of_bins
        if duration_per_bin is not None:
            self._aggregation["durationPerBin"] = duration_per_bin
        if pulses_per_bin is not None:
            self._aggregation["pulsesPerBin"] = pulses_per_bin

    def get_aggregation(self, ):
        return self._aggregation

    def clear(self, ):
        """
        Resets all stored configurations, excluding source_name
        """ 

        self._aggregation = {}

    def get_data(self, channels, start_date="", end_date="", start_pulseid=0, end_pulseid=0, delta_range=1, index_field="globalSeconds", dump_other_index=True):
        # do I want to modify cfg manually???
        df = None
        cfg = {}

        # add aggregation cfg
        if self._aggregation != {}:
            cfg["aggregation"] = self._aggregation
        # add option for date range and pulse_id range, with different indexes
        cfg["channels"] = channels
        cfg["range"] = {}
        
        if (start_date != "" or end_date != "") and (start_pulseid != 0 and end_pulseid != 0):
            raise RuntimeError("Cannot specify both PulseId and Time range")

        if (start_pulseid != 0 or end_pulseid != 0):
            cfg["range"] = _set_pulseid_range(start_pulseid, end_pulseid, delta_range)
        else:
            cfg["range"] = _set_time_range(start_date, end_date, delta_range)

        if not self.is_local:
            response = requests.post(self.source_name + '/sf/query', json=cfg)
            data = response.json()
            self.data = data
            if isinstance(data, dict):
                print("[ERROR]", data["error"])
                try:
                    print("[ERROR]", data["errors"])
                except:
                    pass
                raise RuntimeError(data["message"])
        else:
            data = json.load(open(self.source_name))

        not_index_field = "globalSeconds"
        if index_field == "globalSeconds":
            not_index_field = "pulseId"

        for d in data:
            if dump_other_index:
                if isinstance(d['data'][0]['value'], dict):
                    entry = []
                    keys = sorted(d['data'][0]['value'])
                    for x in d['data']:
                        entry.append([x[index_field], ] + [x['value'][k] for k in keys])
                    #entry = [[x[index_field], x['value']] for x in d['data']]
                    columns = [index_field, ] + [d['channel']['name'] + ":" + k for k in keys]
                    
                else:
                    entry = [[x[index_field], x['value']] for x in d['data']]
                    columns = [index_field, d['channel']['name']]
            else:
                entry = [[x[index_field], x[not_index_field], x['value']] for x in d['data']]
                columns = [index_field, not_index_field, d['channel']['name']]

            if df is not None:
                df2 = pd.DataFrame(entry, columns=columns)
                df2.set_index(index_field, inplace=True)
                df = pd.concat([df, df2], axis=1)
            else:
                df = pd.DataFrame(entry, columns=columns)
                df.set_index(index_field, inplace=True)

        if self.is_local:
            # do the pulse_id, time filtering
            pass

        return df

    def search_channel(self, regex, backends=["sf-databuffer", "sf-archiverappliance"]):
        cfg = {
            "regex": regex,
            "backends": backends,
            "ordering": "asc",
            "reload": "true"
        }

        response = requests.post(self.source_name + '/sf/channels', json=cfg)
        return response.json()
