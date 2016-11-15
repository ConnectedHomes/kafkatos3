'''S3 uploader module'''

import os
import time
import signal
import sys
import traceback
from multiprocessing import Pool

import boto3
# This module seems to have some issues. pylint ignore them
from setproctitle import setproctitle, getproctitle  # pylint: disable=E0611
# pylint: disable=W0703

class S3Uploader(object):
    '''class for uploading files to s3'''

    def __init__(self, config, logger):
        '''constructor'''
        self.config = config
        self.logger = logger
        self.pool = None

    def exit_gracefully(self, signum, frame):
        '''callback to exit gracefully for the main process'''
        self.logger.info("Shutting down S3Uploader, signum %d, frame %d." % (signum, frame))
        if self.pool != None:
            self.logger.info("Terminate the s3uploader worker pool")
            self.pool.terminate()
            self.pool.join()
        sys.exit(0)

    def run(self):
        '''main executor'''
        def exit_gracefully(signum, frame):
            '''callback to exit gracefully for a pool thread'''
            self.logger.info("Shutting down S3Uploader, signum %d, frame %d."% (signum, frame))
            sys.exit(0)

        def init_worker():
            '''callback function to initialise a pool worker'''
            signal.signal(signal.SIGINT, exit_gracefully)
            signal.signal(signal.SIGTERM, exit_gracefully)

            setproctitle("[s3uploadworker] " + getproctitle())

        def upload_file(filename):
            '''upload file'''
            try:
                upload_file_to_s3(filename)
            except KeyboardInterrupt:
                raise
            except Exception as exe:
                self.logger.error("Unexpected error: " + str(exe))
                self.logger.error(traceback.format_exc())
                raise exe

        def upload_file_to_s3(filename):
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


        self.logger.info("S3Uploader process starting up")
        self.pool = Pool(
            int(self.config.get("s3", "s3uploader_workers")), init_worker)

        setproctitle("[s3upload] " + getproctitle())

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        try:
            while True:
                tos3_dir = os.path.join(self.config.get(
                    "main", "working_directory"), "tos3")
                files = self.get_files(tos3_dir, ".gz")
                if files:
                    self.pool.map(upload_file, files)

                time.sleep(float(self.config.get(
                    "s3", "s3upload_check_interval")))
        except KeyboardInterrupt:
            self.pool.terminate()
            self.pool.join()
        except Exception as exe:
            self.logger.error("Unexpected error: " + str(exe))
            self.logger.error(traceback.format_exc())
            self.pool.terminate()
            self.pool.join()
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
