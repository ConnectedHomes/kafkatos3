=========================
 KafkatoS3
=========================

Archive kafka message data to Amazon's s3.

Kafkatos3 is a daemon that connects to Kafka and consumes messages. These messages are written to the disk in a MAK format. At a set interval they are compressed and uploaded to S3.

The purpose of saving the messages is for long term storage for analysis of messages at a later date.

Initially we started looking at programs like secor and bifrost to do this but found they didn't quite meet our requirements so we wrote our own.


Installation Instructions
=========================

- pip install kafkatos3 (tba)
- copy config/kafkatos3.cfg.example to kafkatos3.cfg
- edit kafkatos3.cfg and put in your settings
- Start kafkatos3 with:
    kafkatos3 kafkatos3.cfg


Development Installation Instructions
=====================================

- python setup.py install


Configuration
=============

Kafkatos3 uses the python multiprocess module rather than threading due to GIL limitations. It has three main settings to configure these:

consumer_processes = 1
s3uploader_workers = 1
compressor_workers = 1

To utilise more than one core for consuming messages these should be increased.

Compression
-----------

Currently kafkatos3 calls gzip as an external call to compress the MAK files. This is not configurable yet.


Kafka Consumers
---------------

By default kafatos3 will use the python kafka consumer (https://github.com/dpkp/kafka-python). This can be changed to the C++ kafka consumer (https://github.com/confluentinc/confluent-kafka-python).

This may be more performant than the python consumer although we have not tested this.

In order to install this you will need to pip install confluent-kafka. This requires that the c library from here: https://github.com/edenhill/librdkafka

To switch over the consumer, making the following change in the config file:

consumer_class = KafkaPythonConsumer

to

consumer_class = KafkaConfluentConsumer


Running Over Multiple Instances
===============================

Currently there is no supported way to kafkatos3 to run this on more than one machine. Although the shared storage option would work with limitations (see below).

Possible options for the future:

- With shared storage: This would work fine as long as all instances of kafkatos are using the same consumer group. However currently there is no locking for the compression and s3upload. To get this work currently you'd need to allocate one machine for the compression and one machine for the s3 uploading. The other machines should have their worker count set to 0 to avoid conflicts.

- Without shared storage: The problem with not having shared storage is that kafka can reassign partitions to different consumers at the drop of a hat. This means you might get topicname-0_0-500_160811.mak file on one machine, but a couple of reassignments mid way through could mean you get another file like downstream-0_234-237_160811.mak on another machine. This may not be a problem for you. However, currently with the functionlity the way it is you may end up with orphaned inprogress files that need to be rotated. Only files the daemon is actively locking will get rotated.

- Without shared storage and locked partitions: This solution avoids the problem of kafka assigning different partitions to different boxes randomly by fixing certain partitions to certain machines. However offers no resilience option. This would require some config changes and some tweaks to the consumers.



MAK Format
==========

The MAK (Message Archive Kafka) is a custom format created for the purpose of storing and archiving kafka messages.

This install comes with the following command line util which will parse and print the messages for you:

kafkatos3_parse <filename>.mak

Code examples to parse the mak files yourself can be found in the mak-example directory.

The message form has a header section to describe info about the file and then <key> <message> <offset> repeated over and over again.


Future Plans
============

- Add config options to lock files during compress and upload.
- Add support of kafka 0.8 zookeeper offsets. Old consumer support.
- Add support for kafka 0.10 timestamps in the messages and add to MAK format.
- Add thread to check for unused inprogress files and rotate them out.
- Add support for different compression and compression passwords.

License
=======

TBA

