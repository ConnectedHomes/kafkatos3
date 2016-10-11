
import json
import portalocker
import struct
import os
from collections import namedtuple

KafkaMessage = namedtuple("KafkaMessage",
    ["key", "value", "offset"])

class MessageArchiveKafkaWriter():
   def __init__(self, filename):
     self.filename = filename

     self.latest_offset = None

     seek_number = 0

     if (os.path.isfile(filename) and os.path.getsize(filename)>0):
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
     self.datafile.write_bytes(key)
     self.datafile.write_bytes(value)
     self.datafile.write_int(offset)
     self.update_write_position()
     self.update_latest_offset(offset)

   def close(self):
     self.datafile.close()

   def get_filename(self):
     return self.filename

   def update_latest_offset(self, offset):
     currentPos = self.datafile.tell()
     self.datafile.seek(3, 0)
     self.datafile.write_int(offset)
     self.datafile.seek(currentPos, 0)
     self.latest_offset = offset

   def get_latest_offset(self):
     return self.latest_offset

   def update_write_position(self):
     currentPos = self.datafile.tell()
     self.datafile.seek(11, 0)
     self.datafile.write_int(currentPos)
     self.datafile.seek(currentPos, 0)


class MessageArchiveKafkaReader():
   def __init__(self, filename):
     self.datafile = DataFileReader(filename)
     self.datafile.load()
     self.read_header()

   def has_more_messages(self):
     if self.datafile.tell()>=self.fileend:
         return False
     return True

   def read_header(self):
     data = self.datafile.read_fixed_bytes(3) 
     if data.decode() != "MAK":
       raise "Non-valid MessageArchiveKafka file found"
     self.last_offset = self.datafile.read_int()
     self.fileend = self.datafile.read_int()
     self.headerObj = MessageArchiveKafkaRecord()
     self.headerObj.set_data(self.datafile.read_json())

   def get_header(self): 
     return self.headerObj

   def get_last_offset(self):
     last_pos = self.datafile.tell()
     self.datafile.seek(3, 0)
     offset = self.datafile.read_int()
     self.datafile.seek(last_pos, 0)
     return offset 

   def close(self):
     self.datafile.close()

   def read_message(self):
     key=self.datafile.read_bytes()
     value=self.datafile.read_bytes()
     offset=self.datafile.read_int()

     message=KafkaMessage(key=key, value=value, offset=offset)

     return message


class MessageArchiveKafkaRecord():
   def __init__(self):
     self.data = {}

   def set_data(self, obj):
     self.data=obj

   def get_data(self):
     return self.data

   def set_topic(self, topic):
     self.data['topic']=topic

   def get_topic(self):
     return self.data['topic']

   def set_partition(self, partition):
     self.data['partition']=partition

   def get_partition(self):
     return self.data['partition']

   def set_start_offset(self, offset):
     self.data['startoffset']=offset

   def get_start_offset(self):
     return self.data['startoffset']

   def set_starttime(self, time):
     self.data['starttime']=time

   def get_starttime(self):
     return self.data['starttime'] 


class DataFileReader():
   def __init__(self, filename):
     self.filename = filename

   def load(self):
     self.fh = open(self.filename, 'rb')

   def read_int(self):
     data = self.fh.read(8)
     number = struct.unpack(">Q", data)[0]
     return number

   def read_bytes(self):
     byte_size = self.read_int()
     data = self.fh.read(byte_size)
     return data

   def read_fixed_bytes(self, length):
     data = self.fh.read(length)
     return data 

   def read_string(self):
     rbytes = self.read_bytes()
     return rbytes.decode('utf-8')

   def read_json(self):
     json_string=self.read_string()
     return json.loads(json_string)

   def close(self):
     self.fh.close()

   def seek(self, offset, start):
     self.fh.seek(offset, start)

   def tell(self):
     return self.fh.tell()


class DataFileWriter():
   def __init__(self, filename):
     self.filename = filename

   def open_file(self):
     if os.path.isfile(self.filename):
       self.fh=open(self.filename, 'r+b')
     else:
       self.fh=open(self.filename, 'wb')
     if (portalocker.lock(self.fh, portalocker.LOCK_EX | portalocker.LOCK_NB) == False):
       raise "Unable to get lock on file "+filename

   def write_int(self, number):
     data = struct.pack(">Q", number)
     self.fh.write(data)
     self.fh.flush()

   def write_fixed_bytes(self, wbytes):
     self.fh.write(wbytes)
     self.fh.flush()

   def write_bytes(self, wbytes):

     if wbytes == None:
       self.write_int(0)
       return

     length = len(wbytes)
     self.write_int(length)
     self.fh.write(wbytes)
     self.fh.flush()

   def write_string(self, string):
     wbytes = string.encode(encoding='UTF-8')
     self.write_bytes(wbytes)

   def write_json(self, obj):
     self.write_string(json.dumps(obj))

   def close(self):
     self.fh.close()

   def seek(self, offset, start):
     self.fh.seek(offset, start)

   def tell(self):
     return self.fh.tell()


