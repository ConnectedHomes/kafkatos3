#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Program entry point"""

from __future__ import print_function

# pylint: disable=W0611
# pylint: disable=E0611

import os
import sys
import argparse
import logging
import signal
import ConfigParser
from multiprocessing import Process
# This module seems to have some issues. pylint ignore them
from setproctitle import setproctitle, getproctitle

from kafkatos3.metadata import authors, emails, project, version, url, description

from kafkatos3.Compressor import Compressor
from kafkatos3.S3Uploader import S3Uploader

BASE_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))

class Kafkatos3(object):
    '''main kafkatos3 class'''

    def __init__(self, argv):
        self.argv = argv
        self.config = None
        self.logger = None
        self.processes = []

    def execute(self):
        """Program entry point.

        :param argv: command-line arguments
        :type argv: :class:`list`
        """

        def cb_exit_gracefully(signum, frame):
            '''exit gracefully callback based on signal'''
            self.logger.info("Graceful shutdown of master process started signal %d "\
                             % (signum))
            for process in self.processes:
                process.terminate()
                process.join()
            self.logger.info("Graceful shutdown of master process complete.")
            sys.exit(0)

        def cb_s3_process():
            '''s3 process callback'''
            s3uploader = S3Uploader(self.config, self.logger)
            s3uploader.run()

        def cb_compression_process():
            '''multiprocess callback'''
            mycompressor = Compressor(self.config, self.logger)
            mycompressor.run()

        def cb_consumer_process(consumer_id):
            '''consumer process callback'''
            consumer_class_str = self.config.get("consumer", "consumer_class")

            consumer_class = self.my_import(consumer_class_str+"."+consumer_class_str)
            myconsumer = consumer_class(consumer_id, self.config, self.logger)
            myconsumer.run()

        arg_parser = argparse.ArgumentParser(
            prog=self.argv[0],
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=description,
            epilog=self.get_epilog())
        arg_parser.add_argument(
            '-V', '--version',
            action='version',
            version='{0} {1}'.format(project, version))
        arg_parser.add_argument('configfile', help='kafkatos3 config file to use')

        args = arg_parser.parse_args(args=self.argv[1:])

        self.config = self.parse_config(args.configfile)

        self.logger = logging.getLogger('kafkatos3')
        formatter = logging.Formatter('%(asctime)s - [%(levelname)s/%(processName)s] - %(message)s')
        log_handler = logging.StreamHandler()
        log_handler.setFormatter(formatter)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(log_handler)

        self.logger.info("===============================================================")
        self.logger.info(self.get_epilog())
        self.logger.info("===============================================================")


        for count in range(0, int(self.config.get("consumer", "consumer_processes"))):
            process = Process(target=cb_consumer_process, name='Comsumer'+str(count), \
                      args=(str(count),))
            process.start()
            self.processes.append(process)

        process = Process(target=cb_compression_process, name='Compressor')
        process.start()
        self.processes.append(process)

        process = Process(target=cb_s3_process, name='S3uploader')
        process.start()
        self.processes.append(process)

        setproctitle("[mainprocess] "+getproctitle())

        signal.signal(signal.SIGINT, cb_exit_gracefully)
        signal.signal(signal.SIGTERM, cb_exit_gracefully)

        for process in self.processes:
            process.join()

        return 0


    def my_import(self, import_name):
        '''dynamically import a module'''
        components = import_name.split('.')
        sys.path.append(os.path.dirname(__file__))

        mod = __import__(components[0])
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod

    def parse_config(self, config_file):
        '''Load the kafkatos3 config file'''
        config = ConfigParser.RawConfigParser()
        config.readfp(open(config_file))

        return config

    def get_epilog(self):
        '''get epilog string'''
        author_strings = []
        for name, email in zip(authors, emails):
            author_strings.append('Author: {0} <{1}>'.format(name, email))

        epilog = '''{project} {version}

{authors}
URL: <{url}>
'''.format(project=project,
           version=version,
           authors='\n'.join(author_strings),
           url=url)

        return epilog

def main(argv):
    '''main'''
    kaf = Kafkatos3(argv=argv)
    kaf.execute()

def entry_point():
    """Zero-argument entry point for use with setuptools/distribute."""
    raise SystemExit(main(sys.argv))

if __name__ == '__main__':
    entry_point()
