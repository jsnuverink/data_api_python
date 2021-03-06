import numpy
import bitshuffle
import json
import struct
import h5py
from datetime import datetime

import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# The specification of idread can be found here:
# https://github.psi.ch/sf_daq/idread_specification

# The decoder uses struct.unpack to decode binary values as this proved to be the fastest way to decode

class DictionaryCollector:
    """
    Collector to collect idread data into a dictionary

    Returns a dictionary like this:
    [{"channel":{"name": "", "backend":""}, "data":[{"value": x, "pulse_id": x,...}, ...]},...]
    """
    def __init__(self, event_fields=["value", "time", "pulseId", "status", "severity", "timeRaw"]):
        self.event_fields = event_fields
        self.backend_data = dict()

    def add_data(self, channel_name, backend, value, pulse_id, global_time, ioc_time, status, severity):

        # Internal datastructure used looks like this:
        # backend_data[backend][channel] -> [{"value": x, "pulse_id": ...},...]

        if backend in self.backend_data:
            channel_data = self.backend_data[backend]
        else:
            channel_data = dict()
            self.backend_data[backend] = channel_data

        if channel_name not in channel_data:
            data_list = []
            channel_data[channel_name] = data_list
        else:
            data_list = channel_data[channel_name]

        v = dict()

        for field in self.event_fields:
            if field == "value":
                v["value"] = value
            elif field == "time":         # this is global time globalTime in the idread specification
                # v["time"] = global_time   # TODO to string
                if global_time is not None:
                    v["time"] = datetime.fromtimestamp(global_time / 1e9).astimezone()
                else:
                    v["time"] = global_time
            elif field == "timeRaw":         # this is global time globalTime in the idread specification
                v["timeRaw"] = global_time
            elif field == "pulseId":
                v["pulseId"] = pulse_id
            # elif field == "iocSeconds":  # Not supported any more
            #     v["iocSeconds"] = ioc_time         # TODO to string
            elif field == "status":
                v["status"] = status
            elif field == "severity":
                v["severity"] = severity

        data_list.append(v)

        # if value_name not in self.channel_data[channel_name]:
        #     self.channel_data[channel_name][value_name] = []
        #
        # self.channel_data[channel_name][value_name].append(value)

    def get_data(self):
        data = []
        for backend, channels in self.backend_data.items():
            for channel, data_list in channels.items():
                data.append({"channel": {"name": channel, "backend": backend}, "data": data_list})

        return data


class MappingCollector:
    """
    Collector to collect idread data into a mapping structure

    Returns a dictionary like this:
    [[{"channel": x, "backend": x, "value": x, "pulse_id": x,...}, ...],...]
    """
    def __init__(self, number_of_channels, event_fields=["value", "time", "pulseId", "status", "severity", "timeRaw"]):
        self.event_fields = event_fields
        self.number_of_channels = number_of_channels
        self.backend_data = []

        self.channel_count = 0
        self.tmp_array = []

    def add_data(self, channel_name, backend, value, pulse_id, global_time, ioc_time, status, severity):

        if self.channel_count == self.number_of_channels:
            self.backend_data.append(self.tmp_array)
            self.tmp_array = []
            self.channel_count = 0

        self.channel_count = self.channel_count + 1

        v = None
        if value is not None:
            v = dict()
            v["channel"] = channel_name
            v["backend"] = backend

            for field in self.event_fields:
                if field == "value":
                    v["value"] = value
                elif field == "time":         # this is global time globalTime in the idread specification
                    # v["time"] = global_time   # TODO to string
                    if global_time is not None:
                        v["time"] = datetime.fromtimestamp(global_time / 1e9).astimezone()
                    else:
                        v["time"] = global_time
                elif field == "timeRaw":         # this is global time globalTime in the idread specification
                    v["timeRaw"] = global_time
                elif field == "pulseId":
                    v["pulseId"] = pulse_id
                # elif field == "iocSeconds":  # Not supported any more
                #     v["iocSeconds"] = ioc_time         # TODO to string
                elif field == "status":
                    v["status"] = status
                elif field == "severity":
                    v["severity"] = severity

        self.tmp_array.append(v)

        # if value_name not in self.channel_data[channel_name]:
        #     self.channel_data[channel_name][value_name] = []
        #
        # self.channel_data[channel_name][value_name].append(value)

    def get_data(self):
        # data = []
        # for backend, channels in self.backend_data.items():
        #     for channel, data_list in channels.items():
        #         data.append({"channel": {"name": channel, "backend": backend}, "data": data_list})

        return self.backend_data


class Dataset:
    def __init__(self, name, reference, count=0):
        self.name = name
        self.count = count
        self.reference = reference


class HDF5Collector:
    """
    Collector to write idread based data directly to a hdf5 file
    """

    def __init__(self, compress=False):
        self.file = None
        self.datasets = dict()
        self.compress = compress

    def open(self, file_name):

        if self.file:
            logger.info('File '+self.file.name+' is currently open - will close it')
            self.close_file()

        logger.info('Open file '+file_name)
        self.file = h5py.File(file_name, "w")

    def close(self):
        self.compact_data()

        logger.info('Close file '+self.file.name)
        self.file.close()

    def compact_data(self):
        # Compact datasets, i.e. shrink them to actual size

        for key, dataset in self.datasets.items():
            if dataset.count < dataset.reference.shape[0]:
                logger.info('Compact data for dataset ' + dataset.name + ' from ' + str(dataset.reference.shape[0]) + ' to ' + str(dataset.count))
                dataset.reference.resize(dataset.count, axis=0)

    def append_dataset(self, dataset_name, value, dtype="f8", shape=[1,], compress=False):
        # print(dataset_name, value)

        # Create dataset if not existing
        if dataset_name not in self.datasets:

            dataset_options = {}
            if compress:
                compression = "gzip"
                compression_opts = 5
                shuffle = True
                dataset_options = {'shuffle': shuffle}
                if compression != 'none':
                    dataset_options["compression"] = compression
                    if compression == "gzip":
                        dataset_options["compression"] = compression_opts

            reference = self.file.require_dataset(dataset_name, [1,]+shape, dtype=dtype, maxshape=[None,]+shape, **dataset_options)
            self.datasets[dataset_name] = Dataset(dataset_name, reference)

        dataset = self.datasets[dataset_name]
        # Check if dataset has required size, if not extend it
        if dataset.reference.shape[0] < dataset.count + 1:
            dataset.reference.resize(dataset.count + 1000, axis=0)

        # TODO need to add an None check - i.e. for different frequencies
        if value is not None:
            dataset.reference[dataset.count] = value

        dataset.count += 1

    # def add_data(self, channel_name, value_name, value, dtype="f8", shape=[1, ]):
    #     self.append_dataset('/' + channel_name + '/' + value_name, value, dtype=dtype, shape=shape, compress=self.compress)

    def add_data(self, channel_name, backend, value, pulse_id, global_time, ioc_time, status, severity):
        # TODO Right now ignoring backend!
        self.append_dataset('/' + channel_name + '/data', value,
                            dtype=value.dtype, shape=value.shape, compress=self.compress)
        self.append_dataset('/' + channel_name + '/pulse_id', pulse_id,
                            dtype=pulse_id.dtype, shape=pulse_id.shape, compress=self.compress)
        self.append_dataset('/' + channel_name + '/timestamp', global_time,
                            dtype=global_time.dtype, shape=global_time.shape, compress=self.compress)
        self.append_dataset('/' + channel_name + '/ioc_timestamp', ioc_time,
                            dtype=ioc_time.dtype, shape=ioc_time.shape, compress=self.compress)
        self.append_dataset('/' + channel_name + '/status', status,
                            dtype=status.dtype, shape=status.shape, compress=self.compress)
        self.append_dataset('/' + channel_name + '/severity', ioc_time,
                            dtype=severity.dtype, shape=severity.shape, compress=self.compress)


def decode(bytes, collector_function=None):
    """
    Decode idread decoded data

    :param bytes:              bytes to decode
    :param collector_function: function to collect decoded values. The signature of the function is as follows:
                               def add_data(self, channel_name, backend, value, pulse_id, global_time, ioc_time, status, severity):
    :return:
    """

    channels = None

    while True:
        # read size
        b = bytes.read(8)
        if b == b'':
            logger.debug('End of stream')
            break

        # size = numpy.frombuffer(b, dtype='>i8')
        # size = int.from_bytes(b, byteorder='big')
        size = struct.unpack(">q", b)[0]

        # id = numpy.frombuffer(bytes.read(2), dtype='>i2')
        # id = int.from_bytes(bytes.read(2), byteorder='big')
        id = struct.unpack(">h", bytes.read(2))[0]

        if id == 1:  # Read Header
            header = _read_header(bytes, size)
            logging.debug(header)

            channels = []
            for channel in header['channels']:
                encoding = '>' if 'encoding' in channel and channel["encoding"] == "big" else ''
                n_channel = {}
                if "type" not in channel or channel["type"] == "float64" or channel["type"] == "float":  # default
                    n_channel = {'size': 8, 'dtype': encoding+'f8', 'stype': encoding+'d'}
                elif channel["type"] == "uint8":
                    n_channel = {'size': 1, 'dtype': encoding+'u1', 'stype': encoding+'B'}
                elif channel["type"] == "int8":
                    n_channel = {'size': 1, 'dtype': encoding+'i1', 'stype': encoding+'b'}
                elif channel["type"] == "uint16":
                    n_channel = {'size': 2, 'dtype': encoding+'u2', 'stype': encoding+'H'}
                elif channel["type"] == "int16":
                    n_channel = {'size': 2, 'dtype': encoding+'i2', 'stype': encoding+'h'}
                elif channel["type"] == "uint32":
                    n_channel = {'size': 4, 'dtype': encoding+'u4', 'stype': encoding+'I'}
                elif channel["type"] == "int32":
                    n_channel = {'size': 4, 'dtype': encoding+'i4', 'stype': encoding+'i'}
                elif channel["type"] == "uint64":
                    n_channel = {'size': 8, 'dtype': encoding+'u8', 'stype': encoding+'Q'}
                elif channel["type"] == "int64" or channel["type"] == "int":
                    n_channel = {'size': 8, 'dtype': encoding+'i8', 'stype': encoding+'q'}
                elif channel["type"] == "float32":
                    n_channel = {'size': 4, 'dtype': encoding+'f4', 'stype': encoding+'f'}
                else:
                    # Raise exception for others (including strings)
                    raise RuntimeError('Unsupported data type')

                # need to fix dtype with encoding
                n_channel['encoding'] = encoding
                # n_channel['encoding'] = 'big' if 'encoding' in channel and channel["encoding"] == "big" else 'little'
                # n_channel['dtype'] = n_channel['encoding']+n_channel['dtype']

                n_channel['compression'] = channel['compression'] if 'compression' in channel else None
                # Numpy is slowest dimension first, but bsread is fastest dimension first.
                n_channel['shape'] = channel['shape'][::-1] if 'shape' in channel else [1]

                n_channel['name'] = channel['name']
                n_channel['backend'] = channel['backend']

                # used for struct readout
                n_channel['longtype'] = encoding + 'q'
                n_channel['chartype'] = encoding + 'b'
                n_channel['inttype'] = encoding + 'i'
                channels.append(n_channel)

            logger.debug(channels)

        elif id == 0:  # Read Values

            if channels is None or channel == []:  # Header was not yet received
                bytes.read(int(size - 2))
                logging.warning('No channels specified, cannot deserialize - drop remaining bytes')

            else:
                size_counter = 0
                for channel in channels:

                    # event_size = numpy.frombuffer(bytes.read(4), dtype=channel['encoding']+'i4')
                    # ioc_time = numpy.frombuffer(bytes.read(8), dtype=channel['encoding']+'i8')
                    # pulse_id = numpy.frombuffer(bytes.read(8), dtype=channel['encoding']+'i8')
                    # global_time = numpy.frombuffer(bytes.read(8), dtype=channel['encoding']+'i8')
                    # status = numpy.frombuffer(bytes.read(1), dtype=channel['encoding']+'i1')
                    # severity = numpy.frombuffer(bytes.read(1), dtype=channel['encoding']+'i1')

                    event_size = struct.unpack(channel['inttype'], bytes.read(4))[0]
                    if event_size == 0:
                        ioc_time = None
                        pulse_id = None
                        global_time = None
                        status = None
                        severity = None
                        data = None

                    else:
                        ioc_time = struct.unpack(channel['longtype'], bytes.read(8))[0]
                        pulse_id = struct.unpack(channel['longtype'], bytes.read(8))[0]
                        global_time = struct.unpack(channel['longtype'], bytes.read(8))[0]
                        status = struct.unpack(channel['chartype'], bytes.read(1))[0]
                        severity = struct.unpack(channel['chartype'], bytes.read(1))[0]

                        # number of bytes to subtract from event_size = 8 - 8 - 8 - 1 - 1 = 26
                        n_bytes_to_read = int(event_size-26)
                        raw_bytes = bytes.read(n_bytes_to_read)

                        if channel['compression'] is not None:

                            # TODO need to check for compression type -
                            # Ideally this is done while header parsing, and here I would get the decode function
                            length = struct.unpack(">q", raw_bytes[:8])[0]
                            b_size = struct.unpack(">i", raw_bytes[8:12])[0]

                            data = bitshuffle.decompress_lz4(numpy.frombuffer(raw_bytes[12:],
                                                             dtype=numpy.uint8),
                                                             shape=(channel['shape']),
                                                             dtype=numpy.dtype(channel["dtype"]),
                                                             block_size=b_size / channel['size'])

                        else:
                            if channel['shape'] is None or channel['shape'] == [1]:
                                data = struct.unpack(channel['stype'], raw_bytes)[0]
                            elif len(channel['shape']) == 1:
                                data = struct.unpack(channel['stype'], raw_bytes)
                            else:
                                data = numpy.frombuffer(raw_bytes, dtype=channel["dtype"])
                                data = data.reshape(channel['shape'])

                    size_counter += (2 + 4 + event_size)  # 2 for id, 4 for event_size

                    if collector_function is not None:
                        collector_function(channel['name'], channel["backend"], data, pulse_id, global_time, ioc_time, status, severity)

                remaining_bytes = size-size_counter
                if remaining_bytes > 0:
                    logger.warning("Remaining bytes - %d - drop remaining bytes" % remaining_bytes)
                    bytes.read(remaining_bytes)

        else:

            logging.warning("id %i not supported - drop remaining bytes" % id)
            bytes.read(int(size-2))


def _read_header(byte_array, size):
    hash = numpy.frombuffer(byte_array.read(8), dtype='>i8')
    compression = numpy.frombuffer(byte_array.read(1), dtype='>i1')

    raw_data = byte_array.read(int(size - 2 - 8 - 1))

    if compression == 0:  # header not compressed
        data = raw_data.decode()
    elif compression == 1:  # compressed header
        length = struct.unpack(">q", raw_data[:8])[0]
        b_size = struct.unpack(">i", raw_data[8:12])[0]

        byte_array = bitshuffle.decompress_lz4(numpy.frombuffer(raw_data[12:], dtype=numpy.uint8),
                                               shape=(length,),
                                               dtype=numpy.dtype('uint8'),
                                               block_size=b_size)
        data = byte_array.tobytes().decode()
    else:
        raise RuntimeError('Compression not supported')

    return json.loads(data)
