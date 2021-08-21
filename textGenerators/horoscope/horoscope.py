# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from torolib import torolib
import datetime
import json
import logging
import urllib.request
import random

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.torolib = torolib(redis = redis)
        self.config = self.torolib.getJsonContent(fileName=f'/etc/torobert/{__loader__.name}.config.json')
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
                message['keepAudioFile'] = True
                prefix =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['prefix'], variables=variables)
                if prefix:
                    message["text"] = prefix["text"] + message["text"]
                # the message from the static text collection may be overridden by a horoscope from a website,
                # unless the static horoscope has a high priority (e.g. for birthdays)
                if message.get('prio',3)>=3 and random.random() < self.config.get('chanceForTextFromWebsite',0.67):
                    webHoroscope = self.getWebHoroscope()
                    if webHoroscope:
                        message["text"] = webHoroscope
                        webPrefix =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['webPrefix'], variables=variables)
                        if webPrefix:
                            message["text"] = webPrefix["text"] + message["text"]
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


    def getWebHoroscope(self):
        '''reads a horoscope from a website and returns it as a string'''
        result = None
        try:
            url = self.config['fromWebsite'].get('url')
            logging.debug(f"gathering horoscope from website {url}")
            req = urllib.request.Request(url, data=None, headers={'User-Agent': self.config['fromWebsite'].get('userAgent','')})
            page = urllib.request.urlopen(req)
            soup = BeautifulSoup(page.read(),features="html.parser")
            contentParent = soup.find(self.config['fromWebsite'].get('element','div'),{'class':self.config['fromWebsite'].get('filterClass','')})
            contentChild = contentParent.find('div')
            result = contentChild.get_text(' ')
        except Exception as e:
            logging.error('an error occured while gathering a horoscope: ',exc_info=e)
        return result
