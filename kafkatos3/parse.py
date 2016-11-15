#!/usr/bin/env python
'''test script to parse a mak file'''
import argparse
import sys
from kafkatos3.MessageArchiveKafka import MessageArchiveKafkaReader

def main(argv):
    '''main'''
    parser = argparse.ArgumentParser(
        description='Example script to parse a MAK file', prog=argv[0])
    parser.add_argument('file', help='filename to parse')

    args = parser.parse_args(args=argv[1:])

    makfile = MessageArchiveKafkaReader(args.file)

    header = makfile.get_header()

    print "File topic is " + header.get_topic()
    print "File parition is " + str(header.get_partition())
    print "Staring offset is " + str(header.get_start_offset())
    print "File created at " + str(header.get_starttime())

    while makfile.has_more_messages():
        message = makfile.read_message()
        print "Processing message with offset: " + str(message.offset) + ", key: " + message.key +\
              ", value: " + message.value

def entry_point():
    """Zero-argument entry point for use with setuptools/distribute."""
    raise SystemExit(main(sys.argv))

if __name__ == '__main__':
    entry_point()
