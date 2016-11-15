# -*- coding: utf-8 -*-
"""Project metadata

Information describing the project.
"""
# Project template uses lowercase constants. I'm not going to mess. 
# pylint: disable=C0103 

# The package name, which is also the "UNIX name" for the project.
package = 'kafkatos3'
project = "Kafka to S3"
project_no_spaces = project.replace(' ', '')
version = '0.1.3'
description = 'Archive kafka messages to S3'
authors = ['Ben Corlett', 'Paul Makkar']
authors_string = ', '.join(authors)
emails = ['ben.corlett@bgch.co.uk', 'paul.makkar@bgch.co.uk']
license = 'APACHE 2.0' # pylint: disable=W0622
copyright = '2016 ' + authors_string # pylint: disable=W0622
url = 'https://github.com/ConnectedHomes/kafkatos3'
