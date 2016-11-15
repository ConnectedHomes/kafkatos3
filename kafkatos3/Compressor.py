'''Module used for compressing mak files'''

import os
import time
import signal
import sys
import traceback
import subprocess
from subprocess import Popen, PIPE
from multiprocessing import Pool
# This module seems to have some issues. pylint ignore them
from setproctitle import setproctitle, getproctitle # pylint: disable=E0611

class Compressor(object):
    '''Class to compress our the generated mak files'''

    def move_compressed_file(self, filename):
        '''Move a compressed file out'''
        dest_filename = filename.replace("tocompress", "tos3")
        dest_dirname = os.path.dirname(dest_filename)
        self.mkdirp(dest_dirname)
        self.logger.info("Moving " + filename + " to " + dest_filename)
        try:
            os.rename(filename, dest_filename)
        except OSError as exe:
            self.logger.error("Unexpected error: " + str(exe))
            self.logger.error(traceback.format_exc())

    def mkdirp(self, directory):
        '''Python Equiv of mkdir -p'''
        if not os.path.isdir(directory):
            os.makedirs(directory)

    def __init__(self, config, logger):
        '''Contructor'''
        self.config = config
        self.logger = logger
        self.pool = None
        self.current_subprocs = set()

    def run(self):
        '''Main execute of the class'''
        def init_worker():
            '''Pooled process initialiser callback'''
            signal.signal(signal.SIGINT, exit_gracefully)
            signal.signal(signal.SIGTERM, exit_gracefully)
            setproctitle("[compressworker] " + getproctitle())

        def compress_file(filename):
            '''Pooled process callback to compress a file'''
            move_required = False
            try:
                command = "/usr/bin/nice -n " + \
                    self.config.get("compression", "compression_nice_level") + \
                    " /bin/gzip -f \"" + filename + "\""
                self.logger.info("Command: " + command)
                compress_handle = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
                self.current_subprocs.add(compress_handle)
                compress_handle.communicate()
                move_required = True
                self.current_subprocs.remove(compress_handle)
            except KeyboardInterrupt:
                raise
            except Exception as exe:
                self.logger.error("Unexpected error: " + str(exe))
                self.logger.error(traceback.format_exc())
                raise exe
            finally:
                if move_required:
                    self.move_compressed_file(filename + ".gz")

        def exit_gracefully(signum, frame):
            '''Callback to exit gracefully'''
            self.logger.info("Grace exit command received signum %d frame %d" % (signum, frame))
            for proc in self.current_subprocs:
                if proc.poll() is None:
                    # Switching to a kill -9 as the nice option seems to require it.
                    # proc.send_signal(signal.SIGINT)
                    subprocess.check_call("kill -9 " + proc.pid())
            sys.exit(0)

        self.logger.info("Compressor process starting up")
        self.pool = Pool(
            int(self.config.get("compression", "compressor_workers")), init_worker)

        setproctitle("[compress] " + getproctitle())

        signal.signal(signal.SIGINT, exit_gracefully)
        signal.signal(signal.SIGTERM, exit_gracefully)

        try:
            while True:
                tocompress_dir = os.path.join(self.config.get(
                    "main", "working_directory"), "tocompress")
                files = self.get_files(tocompress_dir, ".mak")

                if files:
                    self.pool.map(compress_file, files, int(
                        self.config.get("compression", "compressor_workers")))

                time.sleep(float(self.config.get(
                    "compression", "compression_check_interval")))
        except KeyboardInterrupt:
            self.pool.terminate()
            self.pool.join()
        sys.exit(0)

    def get_files(self, directory, extension):
        '''Walk files in a directory and return a list of them that match a certain extension'''
        file_list = []
        for dirpath, _, files in os.walk(directory):
            for filename in files:
                fname = os.path.join(dirpath, filename)
                filename, file_extension = os.path.splitext(fname)
                if file_extension == extension:
                    file_list.append(fname)
        return file_list
