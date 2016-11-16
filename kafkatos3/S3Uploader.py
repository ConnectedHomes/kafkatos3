'''S3 uploader module'''

import os
import time
import signal
import sys

import boto3
# This module seems to have some issues. pylint ignore them
from setproctitle import setproctitle, getproctitle  # pylint: disable=E0611

from kafkatos3.ThreadPool import ThreadPool

def upload_file(self, filename):
    '''horrible callback function outside the class because it needs to be pickable'''
    self.upload_file_to_s3(filename)

class S3Uploader(object):
    '''class for uploading files to s3'''

    def __init__(self, config, logger):
        '''constructor'''
        self.config = config
        self.logger = logger
        self.pool = None

    def upload_file_to_s3(self, filename):
        '''upload file to s3'''
        self.logger.info("Uploading file: " + filename + " to s3")

        working_dir = self.config.get("main", "working_directory")

        s3_key = "kafkatos3" + filename.replace(working_dir + "/tos3", "")

        self.logger.info("S3 key is " + s3_key)

        if self.config.get("s3", "s3_access_key") != "":
            access_key = self.config.get("s3", "s3_access_key")
            secret_key = self.config.get("s3", "s3_secret_key")
            s3client = boto3.client("s3", aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key)
        else:
            s3client = boto3.client("s3")

        bucket = self.config.get("s3", "s3_bucket_name")

        s3client.upload_file(filename, bucket, s3_key)

        os.remove(filename)

    def run(self):
        '''main executor'''
        def cb_exit_gracefully(signum, frame):
            '''callback to exit gracefully for a pool thread'''
            self.logger.info("Shutting down S3Uploader, signum %d"% (signum))
            sys.exit(0)

        self.logger.info("S3Uploader process starting up")
        self.pool = ThreadPool(int(self.config.get("s3", "s3uploader_workers")))

        setproctitle("[s3upload] " + getproctitle())

        signal.signal(signal.SIGINT, cb_exit_gracefully)
        signal.signal(signal.SIGTERM, cb_exit_gracefully)

        while True:
            tos3_dir = os.path.join(self.config.get(
                "main", "working_directory"), "tos3")
            files = self.get_files(tos3_dir, ".gz")

            self.pool.map(self.upload_file_to_s3, files)

            time.sleep(float(self.config.get(
                "s3", "s3upload_check_interval")))
        sys.exit(0)

    def get_files(self, directory, extension):
        ''' return a list of files in a directory recusively based on extension'''
        file_list = []
        for dirpath, _, files in os.walk(directory):
            for filename in files:
                fname = os.path.join(dirpath, filename)
                filename, file_extension = os.path.splitext(fname)
                if file_extension == extension:
                    file_list.append(fname)
        return file_list
