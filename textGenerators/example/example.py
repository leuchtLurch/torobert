# -*- coding: utf-8 -*-

from torolib import torolib
import logging

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)


    def getMessageOnRecurrence(self, variables={}):
        logging.info('getText was called')
        return {text:"Früher war mehr Wetter.",prio=3}


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        return {'onDemand': 1}
