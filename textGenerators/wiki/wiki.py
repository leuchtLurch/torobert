# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from torolib import torolib
import datetime
import hashlib
import logging
import json
import random
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
        self.texts = self.torolib.getTextsFromExcel(f'/etc/torobert/{__loader__.name}.texts.xlsx')
        self.textIndices = self.torolib.getTextIndices(self.texts)
        self.topics = self.getTopics()


    def getRandomSummary(self):
        '''returns the text of the summary of a wikipedia page'''
        # randomly pick one of the articles
        topicId = random.randint(0,len(self.topics)-1)
        url = self.config["jsonUrl"] + self.topics[topicId]
        page = urllib.request.urlopen(url)
        data = json.loads(page.read().decode())
        firstPageId = list(data["query"]["pages"].keys())[0]
        summary = data["query"]["pages"][firstPageId]["extract"]
        summary = summary.replace('\r','').replace('\n', ' ').replace('&', ' und ')
        # remove parantheses
        regExp = re.compile(r"(\([^\)]+\))")
        summary = regExp.sub("", summary)
        regExp = re.compile(r"(\[[^\]]+\])")
        summary = regExp.sub("", summary)
        # The whole paragraph is often too long to read. The following section tries to
        # distinguish sentences by finding period-chars followed by capital letters.
        # Then it wants to decide how many sentences are acceptable to read.
        # The sentence recognition is of course not flawless. Some common false posititves include month names (e.g. "4. November"),
        # so they are turned into non capital words before the process starts.
        for nonCapItem in self.config.get("decapitalizeList",[]):
            summary = summary.replace(nonCapItem,nonCapItem.lower())
        summary = re.sub(r"\.\s+([A-ZÄÖÜ])",r". \n\1", summary)
        sentences = summary.split('\n')
        result = sentences[0]
        n = 0
        while len(result) < self.config.get('lengthLimit',330) and n+1< len(sentences):
            n += 1
            if len(result)+len(sentences[n])<self.config.get('lengthLimit',330):
                result += sentences[n]
        logging.debug(f"summary for randomly chosen article: {result}")
        return result


    def getTopics(self):
        '''retrieves a list of wikipedia keywords that can lead to wiki pages'''
        logging.debug('gathering topics from wikipedia')
        page = urllib.request.urlopen(self.config['url'])
        soup = BeautifulSoup(page.read(),features="html.parser")
        topics = []
        for link in soup.find_all('a'):
            href = link.attrs.get('href','')
            if href[0:6] == '/wiki/' and ':' not in href:
                topic = href[6:]
                if topic not in topics:
                    topics.append(topic)
        logging.debug(f"found {len(topics)} topics on wikipedia")
        self.redis.set('wikiLastUpdate',time.time())
        return topics


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        # check if an update of the link list is necessary
        wikiLastUpdate = self.redis.get('wikiLastUpdate')
        if not wikiLastUpdate:
            wikiLastUpdate = b"0"
        if float(wikiLastUpdate) + self.config.get('refreshUrlList',86400) < time.time():
            self.topics = self.getTopics()
        # generate the text content
        summary = None
        n = 0
        while n < 4:
            n += 1
            if not summary:
                summary = self.getRandomSummary()
        if summary:
            prefix = self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['prefix'], variables=variables)
            if prefix:
                prefix = prefix.get('text','')
            else:
                prefix = ''
            return {"text": prefix + summary,"prio":3}
        else:
            return None


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Wikipedia', \
            'fontAwesomeIcon': 'fad fa-atlas', \
            'dynamicSettings' : {
            } \
        }
        return result
