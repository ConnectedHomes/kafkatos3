from multiprocessing import Process, Pool
import os
import time
import signal
import sys
import subprocess
import traceback
import boto3
from setproctitle import setproctitle, getproctitle

# TODO: come up with a better solition here
log = None
conf = None

def exit_gracefully(signum, frame):
  sys.exit(0)

def init_worker():
  signal.signal(signal.SIGINT, exit_gracefully)
  signal.signal(signal.SIGTERM, exit_gracefully)

  setproctitle("[s3uploadworker] "+getproctitle())

def upload_file(filename):
  try:
    upload_file_to_s3(filename)
  except KeyboardInterrupt:
    raise KeyboardInterruptError()
  except Exception as e:
    log.error("Unexpected error: "+str(e))
    log.error(traceback.format_exc())
    raise e

def upload_file_to_s3(filename):
  log.info("Uploading file: "+filename+" to s3")

  working_dir = conf.get("main", "working_directory")

  s3_key = "kafkatos3"+filename.replace(working_dir+"/tos3", "")

  log.info("S3 key is "+s3_key)

  if conf.get("s3", "s3_access_key") != "":
    access_key = conf.get("s3", "s3_access_key")
    secret_key = conf.get("s3", "s3_secret_key")
    c = boto3.client("s3", aws_access_key_id=access_key, aws_secret_access_key=s3_secret_key) 
  else:
    c = boto3.client("s3")

  bucket = conf.get("s3","s3_bucket_name")

  c.upload_file(filename, bucket, s3_key)

  os.remove(filename)


class S3Uploader():

  def __init__(self, config, logger):
    global log
    global conf
    log = logger
    conf = config
    self.config = config
    self.logger = logger
    self.pool = None


  def exit_gracefully(self, signum, frame):
    self.logger.info("Shutting down S3Uploader")
    if self.pool != None:
      self.logger.info("Terminate the s3uploader worker pool")
      self.pool.terminate()
      self.pool.join()
    sys.exit(0)


  def run(self):
    self.logger.info("S3Uploader process starting up")
    self.pool = Pool(int(self.config.get("s3", "s3uploader_workers")), init_worker)

    setproctitle("[s3upload] "+getproctitle())

    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

    try:
      while True:
        tos3_dir = os.path.join(self.config.get("main", "working_directory"),"tos3")
        files = self.get_files(tos3_dir, ".gz")
        if files:
          self.pool.map(upload_file, files)

        time.sleep(float(self.config.get("s3", "s3upload_check_interval")))
    except KeyboardInterrupt:
      self.pool.terminate()
      self.pool.join()
    except Exception as e:
      log.error("Unexpected error: "+str(e))
      log.error(traceback.format_exc())
      self.pool.terminate()
      self.pool.join()
    sys.exit(0)


  def get_files(self, directory, extension):
    file_list = []
    for dirpath, dirs, files in os.walk(directory):
      for filename in files:
        fname = os.path.join(dirpath,filename)
        filename, file_extension = os.path.splitext(fname)
        if file_extension == extension:
          file_list.append(fname)
    return file_list

