# -*- coding: utf-8 -*-

from torolib import torolib
import datetime
import json
import logging

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.torolib = torolib(redis = redis)
        self.texts = self.torolib.getTextsFromExcel(f'/etc/torobert/{__loader__.name}.texts.xlsx')
        self.textIndices = self.torolib.getTextIndices(self.texts)
        self.redis = redis


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        logging.info('getText was called')
        now = datetime.datetime.now()
        # the text of the horoscope needs to stay the same for the length of a day, no matter how often it is read
        # also it should not be read twice on one day even if it is triggered be recurrences more often
        dayLastUsage = self.redis.hget ('horoscope','dayLastUsage')
        if dayLastUsage:
            dayLastUsage = dayLastUsage.decode('ascii')
        else:
            dayLastUsage = ''
        if dayLastUsage == now.strftime('%Y%m%d') and calledBy=='webApp':
            message = self.redis.hget ('horoscope','lastUsedMessage')
            if message:
                message = json.loads(message)
        elif dayLastUsage == now.strftime('%Y%m%d') and calledBy!='webApp':
            message = None
            logging.debug('the horoscope has already been read today, not reading it again')
        else:
            message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['top'], variables=variables)
            if message:
                message['keepAudioFile'] = False
                self.redis.hset ('horoscope','dayLastUsage',now.strftime('%Y%m%d'))
                self.redis.hset ('horoscope','lastUsedMessage',json.dumps(message))
        return message


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Horoskop', \
            'fontAwesomeIcon': 'fas fa-hat-wizard'
        }
        return result
