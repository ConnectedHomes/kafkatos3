#!/usr/bin/env python
import argparse
import sys
from MessageArchiveKafka import MessageArchiveKafkaReader, MessageArchiveKafkaRecord, KafkaMessage

def main(argv):
  parser = argparse.ArgumentParser(description='Example script to parse a MAK file', prog=argv[0])
  parser.add_argument('file', help='filename to parse')

  args = parser.parse_args(args=argv[1:])

  bm = MessageArchiveKafkaReader(args.file)

  header = bm.get_header()

  print "File topic is "+header.get_topic()
  print "File parition is "+str(header.get_partition())
  print "Staring offset is "+str(header.get_start_offset())
  print "File created at "+str(header.get_starttime())

  while bm.has_more_messages():
     message = bm.read_message()
     print "Processing message with offset: "+str(message.offset)+", key: "+message.key+", value: "+message.value


def entry_point():
    """Zero-argument entry point for use with setuptools/distribute."""
    raise SystemExit(main(sys.argv))

if __name__ == '__main__':
    entry_point()

