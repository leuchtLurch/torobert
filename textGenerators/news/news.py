# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from torolib import torolib
import datetime
import hashlib
import logging
import re
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
        self.newsArticles = []


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        # cleanup old entries in the Redis database
        historyNews = self.redis.hgetall ('historyNews')
        if historyNews:
            for historyNewsKey in historyNews.keys():
                if float(historyNews[historyNewsKey]) + self.config['deleteHistoryAfter'] < datetime.datetime.now().timestamp():
                    redis.hdel('historyNews',historyNewsKey)
        # gather new articles from the configured websites
        newsLastUpdate = self.redis.get ('newsLastUpdate')
        if newsLastUpdate:
            newsLastUpdate = float(newsLastUpdate)
        else:
            newsLastUpdate = 0
        if len(self.newsArticles)==0 or (newsLastUpdate + self.config['refreshArticleCache'] < datetime.datetime.now().timestamp()):
            self.newsArticles = []
            try:
                # count how many combinations of urls and filters exist in the config (used for creating the sortkey)
                increment = 0
                for url in self.config['urls'].keys():
                    for articleType in self.config['urls'][url]:
                        increment += 1
                # now lets actually parse some news sites
                offset = 0
                for url in self.config['urls'].keys():
                    logging.debug('gathering news from '+url)
                    req = urllib.request.Request(url, data=None, headers={'User-Agent': self.config.get('userAgent','')})
                    page = urllib.request.urlopen(req)
                    soup = BeautifulSoup(page.read(),features="html.parser")
                    m = 0
                    for articleType in self.config['urls'][url]:
                        offset += 1
                        for content in soup.find_all(articleType.get('element', 'div'),{'class':articleType.get('filterClass','')}):
                            m += 1
                            for e in articleType.get('excludedElements',[]):
                                for trash in content.find_all(e):
                                    trash.decompose()
                            content = content.get_text("|")
                            content = str(content).replace('\n',' ').replace('\r','')
                            # additional string based text replacements
                            for k in articleType.get('replacements', []):
                                if len(k)==2:
                                    content = content.replace(k[0],k[1])
                            # clean the news article, insert separating breaks
                            contentParts = content.split('|')
                            article = ''
                            for contentPart in contentParts:
                                if contentPart.replace('|','').strip() != '':
                                    article += contentPart + self.config['separator']
                            # check if words from the blockList are in the article
                            blockListMatch = False
                            for bockListTerm in articleType.get('bockListTerms',[]):
                                if bockListTerm.lower() in article.lower():
                                    blockListMatch = True
                            # add the article to the list of available articles
                            if article and not blockListMatch:
                                article = article.replace(self.config['separator']+':'+self.config['separator'],self.config['separator'])
                                self.newsArticles.append((m*increment + offset,{'article': article, 'prefixTag': articleType.get('prefixTag', None)}))
                self.newsArticles.sort(key=lambda tup: tup[0])
                self.redis.set ('newsLastUpdate',datetime.datetime.now().timestamp())
                logging.debug('%s articles found' % len(self.newsArticles))
            except Exception as e:
                logging.error('an error occured while gathering news: ',exc_info=e)
        # pick an article to read (one, that has not recently been read)
        articleSelected = False
        n = 0
        while articleSelected==False and n < len(self.newsArticles):
            article = self.newsArticles[n][1].get('article', None)
            articlePrefixTag = self.newsArticles[n][1].get('prefixTag', None)
            articlePrefixText = ""
            if articlePrefixTag:
                articlePrefix=  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=[articlePrefixTag], variables=variables)
                if articlePrefix:
                    articlePrefixText = articlePrefix.get('text','') + self.config['separator']
            articleHash = hashlib.md5(article.encode('utf-8')).hexdigest()
            articleAlreadyRead = self.redis.hget ('historyNews',articleHash)
            if articleAlreadyRead is None and article is not None:
                articleSelected = True
                self.redis.hset ('historyNews',articleHash, datetime.datetime.now().timestamp())
            n += 1
        if articleSelected:
            #print (self.newsArticles)
            return {"text":articlePrefixText + article,"prio":3}
        else:
            return None

    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Nachrichten', \
            'fontAwesomeIcon': 'far fa-newspaper', \
            'dynamicSettings' : {
            } \
        }
        return result
