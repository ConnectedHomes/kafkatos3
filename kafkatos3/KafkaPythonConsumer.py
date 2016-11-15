'''Python consumer'''
import traceback
import time
import os
import signal
import psutil

from setproctitle import setproctitle, getproctitle # pylint: disable=E0611
from kafka import KafkaConsumer
from kafka.consumer.subscription_state import ConsumerRebalanceListener
from kafka.structs import TopicPartition
from kafkatos3.BaseConsumer import BaseConsumer,
from kafkatos3.MessageArchiveKafka import MessageArchiveKafkaRecord, MessageArchiveKafkaReader,\
                                MessageArchiveKafkaWriter


class KafkaPythonConsumer(BaseConsumer, ConsumerRebalanceListener):

    def __init__(self, consumer_id, config, logger):
        BaseConsumer.__init__(consumer_id, config, logger)

    def run_consumer(self):

        bootstrap_server = self.config.get('consumer', 'kafka_bootstrap')
        consumer_group = self.config.get('consumer', 'kafka_consumer_group')

        offset_reset = self.config.get(
            'consumer', 'kafka_auto_offset_reset')
        self.consumer = KafkaConsumer(bootstrap_servers=bootstrap_server,\
                                        consumer_timeout_ms=60000,\
                                        group_id=consumer_group,\
                                        auto_offset_reset=offset_reset)
        topic_whitelist = self.config.get(
            'consumer', 'topic_whitelist')
        self.logger.info("Topic list is " + topic_whitelist)

        self.consumer.subscribe(topic_whitelist.split(","), None, self)

        self.logger.info("Consumer " + self.consumer_id +
                         " starting.... " + str(self.consumer.assignment()))

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        while self.shutting_down == False:
            for message in self.consumer:

                consumer_message = MessageInfo(message.topic, message.partition, message.key,\
                                               message.value, message.offset)
                self.process_message(consumer_message)
                if self.shutting_down == True:
                    break
            self.check_for_rotation()

        for part in self.partitions:
            self.partitions[part].writer.close()

        self.logger.info("Graceful shutdown of consumer " +
                            str(self.consumer_id) + " successful")
    

  

  