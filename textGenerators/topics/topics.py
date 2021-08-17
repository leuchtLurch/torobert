# -*- coding: utf-8 -*-

from torolib import torolib
import logging

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.torolib = torolib(redis = redis)
        self.texts = self.torolib.getTextsFromExcel(f'/etc/torobert/{__loader__.name}.texts.xlsx')
        self.textIndices = self.torolib.getTextIndices(self.texts)


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        logging.info('getText was called')
        message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['topic'], variables=variables)
        if message:
            message['keepAudioFile'] = True # this makes sure that mp3 files are not automatically deleted by the talk module, a good thing for static text
        return message


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 1, \
            'heading': 'Themen', \
            'fontAwesomeIcon': 'fas fa-comments', \
        }
        return result
