
import traceback
import sys
import os
import time
from collections import namedtuple
import psutil

# pylint: disable=W0611
# pylint: disable=E0611
from setproctitle import setproctitle, getproctitle
from kafkatos3.MessageArchiveKafka import MessageArchiveKafkaRecord, MessageArchiveKafkaReader,\
    MessageArchiveKafkaWriter

PartitionInfo = namedtuple("PartitionInfo", ["header", "writer", "offset"])
MessageInfo = namedtuple("MessageInfo", ["topic", "partition", "key", "value", "offset"])

class BaseConsumer(object):
    '''Base consumer class'''

    def __init__(self, consumer_id, config, logger):
        '''constructor'''
        self.consumer_id = consumer_id
        self.config = config
        self.logger = logger
        self.partitions = {}
        self.consumer = None

        self.check_for_rotation_secs = 60
        self.last_rotation_check = 0
        self.shutting_down = False
        self.message_processing = False

        self.last_offset_warning_time = 0

        self.new_file_pending = {}

    def run_consumer(self):
        '''override me'''

    def run(self):
        '''Main class entrypoint'''
        nice_level = self.config.get("consumer", "consumer_nice_level")
        process = psutil.Process(os.getpid())
        process.nice(int(nice_level))

        setproctitle("[consumer" + self.consumer_id + "] " + getproctitle())

        while not self.shutting_down:
            try:
                self.run_consumer()

            except Exception as exe:
                self.logger.error(
                    "Unexpected error with kafka consumer: " + str(exe))
                self.logger.error(traceback.format_exc())
                self.logger.error(
                    "Sleeping for 30 seconds before trying again")
                if self.consumer != None:
                    self.consumer.commit()
                    self.consumer.close()

                for part in self.partitions:
                    self.partitions[part].writer.close()

                time.sleep(30)
        # save all our offsets
        self.consumer.commit()

    def process_message(self, message):
        '''Process a single message returned from a kafka client'''
        self.message_processing = True
        key = message.topic + ':' + str(message.partition)

        if key in self.new_file_pending.keys():
            self.create_new_data_file(self.new_file_pending[key], message.topic, message.partition,\
                                      message.offset)
            del self.new_file_pending[key]

        part_info = self.partitions[key]
        expected_offset = part_info.writer.get_latest_offset()
        if expected_offset != None:
            expected_offset = expected_offset + 1
            if message.offset < expected_offset:
                currenttime = time.mktime(time.gmtime())
                if currenttime > (self.last_offset_warning_time + 10):
                    self.logger.warn("Message offset is lower than the file. Skipping message... "
                                     "topic: "\
                                     + message.topic + ", partition: " + str(message.partition) + \
                                     ", offset: " + str(message.offset) + "(latest in file: " + \
                                     str(expected_offset - 1) + ")")
                    self.logger.warn(
                        "Surpressing further offset warnings for the next 10 seconds")
                self.last_offset_warning_time = currenttime
                return
            if message.offset > expected_offset:
                self.logger.error("We have missing messages! topic: " + message.topic + \
                                  ", partition: " + str(message.partition) + ", offset: " + \
                                  str(message.offset) + " (latest in file: " + \
                                  str(expected_offset - 1) + ")")

        self.logger.debug("Writing to "+key+" with key of "+message.key)
        part_info.writer.write_message(message.offset, message.key, message.value)
        part_info = part_info._replace(offset=message.offset)
        self.partitions[key] = part_info
        self.check_for_rotation()
        self.message_processing = False

    def exit_gracefully(self, signum, frame):
        '''exit the consumer gracefully'''
        if not self.message_processing:
            self.logger.info("Fast shutdown available ... exiting (signum %d)" \
                             % (signum))
            self.logger.info("Print stack trace. Don't panic!")
            self.logger.info("-----------------------------------------------")
            for chunk in traceback.format_stack(frame):
                for line in chunk.split("\n"):
                    self.logger.info(line)
            self.logger.info("-----------------------------------------------")
            for part in self.partitions:
                self.partitions[part].writer.close()
            self.consumer.commit()
            sys.exit(0)

        self.logger.info("Graceful shutdown of consumer " +
                         str(self.consumer_id) + " started....")
        self.shutting_down = True

    def check_for_rotation(self):
        '''check partition for rotation'''
        current_time = time.mktime(time.gmtime())
        if current_time < (self.last_rotation_check + self.check_for_rotation_secs):
            return
        for k in self.partitions:
            if current_time > (int(self.partitions[k].header.get_starttime()) + \
                               int(self.config.get("consumer", "max_age_seconds"))):
                self.rotate_partition(k)


    def rotate_partition(self, partition):
        '''rotate a partition'''
        topic = self.partitions[partition].header.get_topic()
        part_number = self.partitions[partition].header.get_partition()

        key = topic + ":" + str(part_number)

        if key in self.new_file_pending.keys():
            self.logger.debug("File has not been created yet. Don't rotate")
            return

        if int(self.partitions[partition].offset) ==\
            int(self.partitions[partition].header.get_start_offset()):
            self.logger.debug("Skiping rotate for partition " +
                              partition + ". No new writes")
            return
        self.logger.info("I need to rotate " + partition)
        self.partitions[partition].writer.close()

        start_offset = self.partitions[partition].header.get_start_offset()
        end_offset = self.partitions[partition].offset

        dest_dir = os.path.join(self.config.get(
            "main", "working_directory"), "tocompress", topic, str(part_number))

        date = time.strftime("%y%m%d")

        dest_filename = os.path.join(dest_dir, topic + "-" + str(part_number) + "_" + str(
            start_offset) + "-" + str(end_offset) + "_" + date + ".mak")

        self.mkdirp(dest_dir)

        os.rename(self.partitions[partition].writer.get_filename(), dest_filename)

        self.create_new_data_file(self.partitions[partition].writer.get_filename(),\
                                  topic, part_number, end_offset + 1)

    def mkdirp(self, directory):
        '''equiv of mkdir -p'''
        if not os.path.isdir(directory):
            os.makedirs(directory)

    def create_new_data_file(self, fullname, topic, partition, offset):
        '''create a new data file'''
        header = MessageArchiveKafkaRecord()
        header.set_topic(topic)
        header.set_partition(partition)
        header.set_start_offset(offset)
        last_offset = offset
        header.set_starttime(time.mktime(time.gmtime()))
        bmw = MessageArchiveKafkaWriter(fullname)
        bmw.write_header(header)

        part_info = PartitionInfo(
            header=header, writer=bmw, offset=last_offset)
        key = topic + ":" + str(partition)
        self.partitions[key] = part_info

    def get_part_list_string(self, items):
        '''return a string list for the topic partitions'''
        comma = ""
        return_str = ""
        for topic_part in items:
            return_str = return_str + comma + topic_part.topic + ":" + str(topic_part.partition)
            comma = ", "
        return return_str

    def on_partitions_assigned(self, assigned):
        '''callback for partitions assigned'''
        try:
            self.logger.info("Consumer " + str(self.consumer_id) +
                             " got assigned: " + self.get_part_list_string(assigned))

            for topic_partition in assigned:

                working_dir = self.config.get("main", "working_directory")

                filedir = os.path.join(working_dir, "inprogress", topic_partition.topic,\
                                       str(topic_partition.partition))
                fullname = os.path.join(filedir, "data.mak")

                key = topic_partition.topic + ":" + \
                    str(topic_partition.partition)
                if key in self.partitions.keys():
                    self.logger.debug("Already managing topic:  " + topic_partition.topic +\
                                      ", parition: " + str(topic_partition.partition) +\
                                      " ... do nothing")
                    continue

                if os.path.exists(fullname):
                    self.logger.debug("Resuming from existing file for topic: " +
                                      topic_partition.topic + ", parition: " +\
                                      str(topic_partition.partition))
                    bmr = MessageArchiveKafkaReader(fullname)
                    header = bmr.get_header()
                    last_offset = bmr.get_last_offset()
                    bmr.close()
                    bmw = MessageArchiveKafkaWriter(fullname)

                    part_info = PartitionInfo(
                        header=header, writer=bmw, offset=last_offset)
                    self.partitions[key] = part_info

                else:
                    self.logger.debug("Creating new file for topic: " + topic_partition.topic +
                                      ", parition: " + str(topic_partition.partition))

                    self.mkdirp(filedir)
                    self.new_file_pending[key] = fullname

        except Exception as exe:
            self.logger.error("Unexpected error: " + str(exe))
            self.logger.error(traceback.format_exc())
            raise

    def on_partitions_revoked(self, revoked):
        '''callback for partitions revoked'''
        try:
            self.logger.info("Consumer " + str(self.consumer_id) +
                             " got revoked: " + self.get_part_list_string(revoked))

            for topic_partition in revoked:
                key = topic_partition.topic + ":" + \
                    str(topic_partition.partition)
                if key in self.partitions.keys():
                    self.partitions[key].writer.close()
                    del self.partitions[key]

        except Exception as exe:
            self.logger.error("Unexpected error: " + str(exe))
            self.logger.error(traceback.format_exc())
            raise
