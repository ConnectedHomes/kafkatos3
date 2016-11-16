'''Module used for compressing mak files'''

import os
import time
import signal
import sys
import traceback
from subprocess import Popen, PIPE

# setproctitle module seems to have some issues. pylint ignore them
# pylint: disable=W0611
# pylint: disable=E0611

from kafkatos3.ThreadPool import ThreadPool

from setproctitle import setproctitle, getproctitle


class Compressor(object):
    '''Class to compress our the generated mak files'''

    def __init__(self, config, logger):
        '''Contructor'''
        self.config = config
        self.logger = logger
        self.pool = None
        self.current_subprocs = set()

    def compress_filename(self, filename):
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
            if compress_handle.returncode != 0:
                raise Exception("Compression failed for file "+filename)
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

    def run(self):
        '''Main execute of the class'''

        def cb_exit_gracefully(signum, frame):
            '''Callback to exit gracefully'''
            self.logger.info("Grace exit command received signum %d" % (signum))
            for proc in self.current_subprocs:
                if proc.poll() is None:
                    # Switching to a kill -9 as the nice option seems to require it.
                    # proc.send_signal(signal.SIGINT)
                    proc.terminate()
                    #subprocess.check_call("kill -9 " + proc.pid())
            sys.exit(0)

        compressor_workers = int(self.config.get("compression", "compressor_workers"))

        self.logger.info("Compressor process starting up")
        self.pool = ThreadPool(compressor_workers)

        setproctitle("[compress] " + getproctitle())

        signal.signal(signal.SIGINT, cb_exit_gracefully)
        signal.signal(signal.SIGTERM, cb_exit_gracefully)

        while True:
            tocompress_dir = os.path.join(self.config.get(
                "main", "working_directory"), "tocompress")
            files = self.get_files(tocompress_dir, ".mak")

            if files:
                self.pool.map(self.compress_filename, files)

            time.sleep(float(self.config.get(
                "compression", "compression_check_interval")))
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
