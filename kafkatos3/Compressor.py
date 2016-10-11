from multiprocessing import Process, Pool
import os
import time
import signal
import sys
import subprocess
import traceback
from setproctitle import setproctitle, getproctitle
from subprocess import Popen, PIPE

log = None
conf = None
current_subprocs = set()

def exit_gracefully(signum, frame):
  global current_subprocs
  for proc in current_subprocs:
    if proc.poll() is None:
      # Switching to a kill -9 as the nice option seems to require it.
      # proc.send_signal(signal.SIGINT)
      subprocess.check_call("kill -9 "+proc.pid())
  sys.exit(0)

def init_worker():
  signal.signal(signal.SIGINT, exit_gracefully)
  signal.signal(signal.SIGTERM, exit_gracefully)
  setproctitle("[compressworker] "+getproctitle())

def compress_file(filename):
  global current_subprocs
  move_required=False
  try:
    command = "/usr/bin/nice -n "+conf.get("compression", "compression_nice_level")+" /bin/gzip -f \""+filename+"\""
    log.info("Command: "+command)
    p = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
    current_subprocs.add(p)
    out, err = p.communicate()
    move_required=True
    current_subprocs.remove(p) 
  except KeyboardInterrupt:
    raise KeyboardInterruptError()
  except Exception as e:
    log.error("Unexpected error: "+str(e))
    log.error(traceback.format_exc())
    raise e
  finally:
    try:
      if move_required == True:
        move_compressed_file(filename+".gz")
    except Exception as e:
      log.error("Unexpected error: "+str(e))
      log.error(traceback.format_exc())

def move_compressed_file(filename):
  dest_filename = filename.replace("tocompress", "tos3")
  dest_dirname = os.path.dirname(dest_filename)
  mkdirp(dest_dirname)
  log.info("Moving "+filename+" to "+dest_filename)
  os.rename(filename, dest_filename)

def mkdirp(directory):
  if not os.path.isdir(directory):
    os.makedirs(directory)


class Compressor():

  def __init__(self, config, logger):
    global log
    global conf
    log = logger
    conf = config
    self.config = config
    self.logger = logger
    self.pool = None


  def exit_gracefully(self, signum, frame):
    self.logger.info("Shutting down Compressor")
    if self.pool != None:
      self.logger.info("Terminate the compressor worker pool")
      self.pool.terminate()
      self.pool.join()
    sys.exit(0)


  def run(self):
    self.logger.info("Compressor process starting up")
    self.pool = Pool(int(self.config.get("compression", "compressor_workers")),init_worker)

    setproctitle("[compress] "+getproctitle())

    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

    try:
      while True:
        tocompress_dir = os.path.join(self.config.get("main", "working_directory"),"tocompress")
        files = self.get_files(tocompress_dir, ".mak")

        if files:
          self.pool.map(compress_file, files, int(self.config.get("compression", "compressor_workers")))

        time.sleep(float(self.config.get("compression", "compression_check_interval")))
    except KeyboardInterrupt:
      self.pool.terminate()
      self.pool.join()
    sys.exit(0)

  def compress_file(self, filename):
    self.logger.info("Compressing file: "+filename)
    time.sleep(1)


  def get_files(self, directory, extension):
    file_list = []
    for dirpath, dirs, files in os.walk(directory):
      for filename in files:
        fname = os.path.join(dirpath,filename)
        filename, file_extension = os.path.splitext(fname)
        if file_extension == extension:
          file_list.append(fname)
    return file_list

