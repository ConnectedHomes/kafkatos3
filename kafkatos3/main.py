#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Program entry point"""

from __future__ import print_function

import os
import sys
import argparse
import sys
import logging
import multiprocessing
import ConfigParser
from multiprocessing import Process, Pool
import signal
from setproctitle import setproctitle, getproctitle

import metadata
#from kafkatos3 import metadata

from Compressor import Compressor
from S3Uploader import S3Uploader


base_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
config = None
logger = None
processes = []

def main(argv):
    global config
    global logger
    """Program entry point.

    :param argv: command-line arguments
    :type argv: :class:`list`
    """
    author_strings = []
    for name, email in zip(metadata.authors, metadata.emails):
        author_strings.append('Author: {0} <{1}>'.format(name, email))

    epilog = '''{project} {version}

{authors}
URL: <{url}>
'''.format(
        project=metadata.project,
        version=metadata.version,
        authors='\n'.join(author_strings),
        url=metadata.url)

    arg_parser = argparse.ArgumentParser(
        prog=argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=metadata.description,
        epilog=epilog)
    arg_parser.add_argument(
        '-V', '--version',
        action='version',
        version='{0} {1}'.format(metadata.project, metadata.version))
    arg_parser.add_argument('configfile', help='kafkatos3 config file to use')

    args=arg_parser.parse_args(args=argv[1:])

    config = parse_config(args.configfile)

    logger = logging.getLogger('kafkatos3')
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s/%(processName)s] - %(message)s')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(ch)

    logger.info("===============================================================")
    logger.info(epilog)
    logger.info("===============================================================")

    for x in range(0, int(config.get("consumer", "consumer_processes"))):
      p = Process(target=consumer_process, args=(str(x),))
      p.start()
      processes.append(p)

    p = Process(target=compression_process)
    p.start()
    processes.append(p)

    p = Process(target=s3_process)
    p.start()
    processes.append(p)

    setproctitle("[mainprocess] "+getproctitle())

    for p in processes:
      p.join()

    return 0

def parse_config(config_file):
    config = ConfigParser.RawConfigParser()
    config.readfp(open(config_file))

    return config


def exit_gracefully(signum, frame):
    logger.info("Graceful shutdown of master process started....")
    for p in processes:
      p.terminate()
      p.join()
    logger.info("Graceful shutdown of master process complete.")
    sys.exit(0)


def compression_process():
    global config
    global logger
    mycompressor = Compressor(config, logger)
    mycompressor.run()


def s3_process():
    global config
    global logger
    s3uploader = S3Uploader(config, logger)
    s3uploader.run()


def my_import(name):
    global logger
    components = name.split('.')
    sys.path.append(os.path.dirname(__file__))

    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def consumer_process(consumer_id):
    consumerClassStr = config.get("consumer", "consumer_class")

    consumerClass = my_import(consumerClassStr+"."+consumerClassStr)

    myconsumer = consumerClass(consumer_id, config, logger)
    myconsumer.run()


def entry_point():
    """Zero-argument entry point for use with setuptools/distribute."""
    raise SystemExit(main(sys.argv))


if __name__ == '__main__':
    entry_point()
