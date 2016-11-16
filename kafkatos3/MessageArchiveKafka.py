'''module with classes to read and write to mak files'''
import json
import struct
import os
from collections import namedtuple

import portalocker

KafkaMessage = namedtuple("KafkaMessage",
                          ["key", "value", "offset"])

class MessageArchiveKafkaWriter(object):
    '''Class to write to a MAK file'''

    def __init__(self, filename):
        ''''constuctor'''
        self.filename = filename

        self.latest_offset = None

        seek_number = 0

        if os.path.isfile(filename) and os.path.getsize(filename) > 0:
            readfile = DataFileReader(filename)
            readfile.load()

            readfile.seek(3, 0)
            self.latest_offset = readfile.read_int()

            readfile.seek(11, 0)
            seek_number = readfile.read_int()
            readfile.close()

        self.datafile = DataFileWriter(filename)
        self.datafile.open_file()
        self.datafile.seek(seek_number, 0)

    def write_header(self, header):
        '''write the MAK header to the data file'''
        data = "MAK".encode()
        self.datafile.write_fixed_bytes(data)

        # next 64 bits reserved for latest offset
        self.datafile.write_int(header.get_start_offset())

        # next 64 bits reserved for point in file to write the next record
        # we don't know it yet so we go 0 and correct later
        self.datafile.write_int(0)

        self.datafile.write_json(header.get_data())

        self.update_write_position()

    def write_message(self, offset, key, value):
        '''write a kafka message to the MAK file'''
        self.datafile.write_bytes(key)
        self.datafile.write_bytes(value)
        self.datafile.write_int(offset)
        self.update_write_position()
        self.update_latest_offset(offset)

    def close(self):
        '''close the MAK file'''
        self.datafile.close()

    def get_filename(self):
        '''return the filename of the currentl MAK file'''
        return self.filename

    def update_latest_offset(self, offset):
        '''update the offset in the header'''
        current_pos = self.datafile.tell()
        self.datafile.seek(3, 0)
        self.datafile.write_int(offset)
        self.datafile.seek(current_pos, 0)
        self.latest_offset = offset

    def get_latest_offset(self):
        '''get the last offset written to the file'''
        return self.latest_offset

    def update_write_position(self):
        '''set the last write position'''
        current_pos = self.datafile.tell()
        self.datafile.seek(11, 0)
        self.datafile.write_int(current_pos)
        self.datafile.seek(current_pos, 0)


class MessageArchiveKafkaReader(object):

    '''Class to read from a MAK file'''

    def __init__(self, filename):
        '''constructor'''
        self.datafile = DataFileReader(filename)
        self.datafile.load()
        self.read_header()

    def has_more_messages(self):
        '''returns True, False depending upon if any more messages existing when walking the file'''
        if self.datafile.tell() >= self.fileend:
            return False
        return True

    def read_header(self):
        '''read the MAK header'''
        data = self.datafile.read_fixed_bytes(3)
        if data.decode() != "MAK":
            raise "Non-valid MessageArchiveKafka file found"
        self.last_offset = self.datafile.read_int()
        self.fileend = self.datafile.read_int()
        self.header_obj = MessageArchiveKafkaRecord()
        self.header_obj.set_data(self.datafile.read_json())

    def get_header(self):
        '''return the header information'''
        return self.header_obj

    def get_last_offset(self):
        '''get the last offset position written to the file'''
        last_pos = self.datafile.tell()
        self.datafile.seek(3, 0)
        offset = self.datafile.read_int()
        self.datafile.seek(last_pos, 0)
        return offset

    def close(self):
        '''close the MAK file'''
        self.datafile.close()

    def read_message(self):
        '''read the next message and return a KafkaMessage'''
        key = self.datafile.read_bytes()
        value = self.datafile.read_bytes()
        offset = self.datafile.read_int()

        message = KafkaMessage(key=key, value=value, offset=offset)

        return message


class MessageArchiveKafkaRecord(object):
    '''Class to represent a MAK file header'''

    def __init__(self):
        '''constructor'''
        self.data = {}

    def set_data(self, obj):
        '''set the data section of the header'''
        self.data = obj

    def get_data(self):
        '''get the data section of the header'''
        return self.data

    def set_topic(self, topic):
        '''set the kafka topic for the header'''
        self.data['topic'] = topic

    def get_topic(self):
        '''get the kafka topic used in the header'''
        return self.data['topic']

    def set_partition(self, partition):
        '''set the partition id of the MAK file'''
        self.data['partition'] = partition

    def get_partition(self):
        '''get the parition id of the MAK file'''
        return self.data['partition']

    def set_start_offset(self, offset):
        '''set the starting offset of this file'''
        self.data['startoffset'] = offset

    def get_start_offset(self):
        '''get the starting offset of the MAK file'''
        return self.data['startoffset']

    def set_starttime(self, time):
        '''set the start time of the MAK file'''
        self.data['starttime'] = time

    def get_starttime(self):
        '''get the startime of the MAK file'''
        return self.data['starttime']


class DataFileReader(object):
    '''generic binary data file reader class'''

    def __init__(self, filename):
        '''contructor'''
        self.filename = filename
        self.file_handle = None

    def load(self):
        '''Load file by filename'''
        self.file_handle = open(self.filename, 'rb')

    def read_int(self):
        '''read a 64 bit integer from the file'''
        data = self.file_handle.read(8)
        number = struct.unpack(">Q", data)[0]
        return number

    def read_bytes(self):
        '''read a 64 bit integer as a byte count and read that about of bytes from the file'''
        byte_size = self.read_int()
        data = self.file_handle.read(byte_size)
        return data

    def read_fixed_bytes(self, length):
        '''read a fixed length set of bytes'''
        data = self.file_handle.read(length)
        return data

    def read_string(self):
        '''read a string from the file'''
        rbytes = self.read_bytes()
        return rbytes.decode('utf-8')

    def read_json(self):
        '''read a json from the file'''
        json_string = self.read_string()
        return json.loads(json_string)

    def close(self):
        '''close the file'''
        self.file_handle.close()

    def seek(self, offset, start):
        '''seek to a specific file offset'''
        self.file_handle.seek(offset, start)

    def tell(self):
        '''return the current file position'''
        return self.file_handle.tell()


class DataFileWriter(object):
    '''Generic class to write to a data file'''
    def __init__(self, filename):
        '''constructor'''
        self.filename = filename
        self.file_handle = None

    def open_file(self):
        '''open file for writing'''
        if os.path.isfile(self.filename):
            self.file_handle = open(self.filename, 'r+b')
        else:
            self.file_handle = open(self.filename, 'wb')
        try:
            portalocker.lock(self.file_handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException as exp:
            raise exp

    def write_int(self, number):
        '''Write a 64 bit integer to the file'''
        data = struct.pack(">Q", number)
        self.file_handle.write(data)
        self.file_handle.flush()

    def write_fixed_bytes(self, wbytes):
        '''Write a series of bytes to the file'''
        self.file_handle.write(wbytes)
        self.file_handle.flush()

    def write_bytes(self, wbytes):
        '''write a 64 bit integer as a byte count and write that about of bytes from the file'''
        if wbytes is None:
            self.write_int(0)
            return

        length = len(wbytes)
        self.write_int(length)
        self.file_handle.write(wbytes)
        self.file_handle.flush()

    def write_string(self, string):
        '''write a fixed length set of bytes'''
        wbytes = string.encode(encoding='UTF-8')
        self.write_bytes(wbytes)

    def write_json(self, obj):
        '''write a json obj to the file'''
        self.write_string(json.dumps(obj))

    def close(self):
        '''close the file handle'''
        self.file_handle.close()

    def seek(self, offset, start):
        '''seek to a specific part of the file'''
        self.file_handle.seek(offset, start)

    def tell(self):
        '''return the current file position'''
        return self.file_handle.tell()
