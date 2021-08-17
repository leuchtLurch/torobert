# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from torolib import torolib
import datetime
import hashlib
import logging
import re
import time
import urllib.request

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.redis = redis
        self.torolib = torolib(redis = redis)
        self.config = self.torolib.getJsonContent(fileName=f'/etc/torobert/{__loader__.name}.config.json')
        self.texts = self.torolib.getJsonContent(f'/etc/torobert/{__loader__.name}.texts.json')
        self.textIndices = self.torolib.getTextIndices(self.texts)


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        timeLastUsage = self.redis.hget ('weather','timeLastUsage')
        if timeLastUsage:
            timeLastUsage = float(timeLastUsage)
        else:
            timeLastUsage = 0
        if timeLastUsage + self.config.get("cooldownPeriod",86400) < time.time() or calledBy=='webApp':
            url = self.config.get('url')
            if url is None:
                return None
            logging.debug('gathering weather from '+url)
            content = None
            try:
                page = urllib.request.urlopen(url)
                soup = BeautifulSoup(page.read(),features="html.parser")
                content = soup.find(self.config.get('element', 'div'),{'class':self.config.get('filterClass','')})
            except Exception as e:
                logging.error('An Error occured while gathering the weather report: ',exc_info=e)
            if content:
                weather = ''
                for child in content.descendants:
                    weather = weather + str(child).replace('\n',' ').replace('\r','').strip() + self.config.get('separator', ' ')
                for e in self.config.get('excludedElements',[]):
                    regex = re.compile(r"<%s\s.*?/%s>" % (e, e), re.IGNORECASE)
                    weather = regex.sub("", weather)
                prefix =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['prefix'], variables=variables)
                if prefix:
                    prefixText = prefix.get('text') + self.config.get('separator', ' ')
                else:
                    prefixText = ''
                self.redis.hset ('weather','timeLastUsage', time.time())
                return {"text": prefixText + weather,"prio":3}
            else:
                logging.warning('No weather report could be found on the provided url.')
                return None
        else:
            logging.debug("the weather has already been read recently, so I will not read it again")
            return None


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Wetter', \
            'fontAwesomeIcon': 'fas fa-cloud-sun-rain', \
            'dynamicSettings' : {
            } \
        }
        return result
