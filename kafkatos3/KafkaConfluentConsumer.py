'''Kafka confluent consumer. Dependant on librdkafka'''
import signal

# pylint: disable=W0611
# pylint: disable=E0611
from confluent_kafka import Consumer, KafkaError
from setproctitle import setproctitle, getproctitle
from kafkatos3.BaseConsumer import BaseConsumer, MessageInfo

class KafkaConfluentConsumer(BaseConsumer):

    '''Kafka confluent consuemr'''

    def __init__(self, consumer_id, config, logger):
        BaseConsumer.__init__(self, consumer_id, config, logger)

    def run_consumer(self):
        '''core consumer code'''

        def cb_on_assign(consumer, partitions):
            '''topic on assign callback'''
            self.on_partitions_assigned(partitions)

        def cb_on_revoke(consumer, partitions):
            '''topic on revoke callback'''
            self.on_partitions_revoked(partitions)

        offset_reset = self.config.get(
            'consumer', 'kafka_auto_offset_reset')

        bootstrap_server = self.config.get('consumer', 'kafka_bootstrap')
        consumer_group = self.config.get('consumer', 'kafka_consumer_group')

        conf = {'bootstrap.servers': bootstrap_server, 'group.id': consumer_group,
                'default.topic.config': {'auto.offset.reset': offset_reset}}

        self.consumer = Consumer(**conf)

        topic_whitelist = self.config.get(
            'consumer', 'topic_whitelist')
        self.logger.info("Topic list is " + topic_whitelist)

        self.consumer.subscribe(topic_whitelist.split(
            ","), on_assign=cb_on_assign, on_revoke=cb_on_revoke)

        self.logger.info("Consumer " + self.consumer_id + " starting.... ")

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        while not self.shutting_down:
            message = self.consumer.poll(timeout=60.0)
            if message is None:
                self.check_for_rotation()
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    self.logger.debug('%% %s [%d] reached end at offset %d\n' % (
                        message.topic(), message.partition(), message.offset()))
                else:
                    raise Exception(message.error())
            else:
                consumer_message = MessageInfo(message.topic(), message.partition(), message.key(),\
                                               message.value(), message.offset())
                self.process_message(consumer_message)
                if self.shutting_down:
                    break

        for part in self.partitions:
            self.partitions[part].writer.close()

        self.logger.info("Graceful shutdown of consumer " + str(self.consumer_id) + " successful")






