# -*- coding: utf-8 -*-

from torolib import torolib
import logging
import random

class textGenerator(object):

    def __init__(self, redis):
        self.log = logging.getLogger(__name__)
        self.log.info('initializing textGenerator extension ' + __loader__.name)
        self.torolib = torolib(redis = redis)
        self.config = self.torolib.getJsonContent(fileName=f'/etc/torobert/{__loader__.name}.config.json')
        #self.texts = self.torolib.getJsonContent(f'textGenerators/{__loader__.name}/texts.json')
        self.texts = self.torolib.getTextsFromExcel(f'/etc/torobert/{__loader__.name}.texts.xlsx')
        self.textIndices = self.torolib.getTextIndices(self.texts)


    def getMessageOnInit(self):
        '''returns a message to be read immediately after this textGenerator extension is initialied (bootup greeting)'''
        message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['bootupGreeting'])
        return message


    def getMessageOnReactivation(self, variables={}):
        '''returns a message to be read when toroberts motion sensor is triggered after a longer period of inactivity (welcome back greeting)'''
        message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['greeting'], variables=variables)
        if not message:
            message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['top'], variables=variables)
        return message


    def getMessageOnRecurrence(self, variables={}, calledBy=''):
        '''returns a message to be read, is triggered on recurring intervals during normal operations or by the webApp'''
        if random.random() < float(self.config.get('chanceOfExecution',0.2)):
            logging.info('getText was called')
            message =  self.torolib.buildMessage(texts = self.texts, textIndices = self.textIndices, tags=['top'], variables=variables)
        else:
            logging.info('getText was called - but silenced by chance')
            message = None
        #if message:
            #message['keepAudioFile'] = True # this makes sure that mp3 files are not automatically deleted by the talk module, a good thing for static text
        return message


    def getWebAppConfig(self):
        '''returns a dict which tells torobert how to make this textGenerator configurable through the dynamic configuration website'''
        result = { \
            'onDemand': 0, \
            'heading': 'Quasseln', \
            'fontAwesomeIcon': 'fas fa-comment-dots' \
        }
        return result
