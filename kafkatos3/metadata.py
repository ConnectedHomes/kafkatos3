# -*- coding: utf-8 -*-
"""Project metadata

Information describing the project.
"""
# Project template uses lowercase constants. I'm not going to mess. 
# pylint: disable=C0103

# pylint: disable=I0011,W0622

# The package name, which is also the "UNIX name" for the project.
package = 'kafkatos3'
project = "Kafka to S3"
project_no_spaces = project.replace(' ', '')
version = '0.1.4'
description = 'Archive kafka messages to S3'
authors = ['Ben Corlett', 'Paul Makkar']
authors_string = ', '.join(authors)
emails = ['ben.corlett@bgch.co.uk', 'paul.makkar@bgch.co.uk']
license = 'APACHE 2.0'
copyright = '2016 ' + authors_string
url = 'https://github.com/ConnectedHomes/kafkatos3'
