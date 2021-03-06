# -*- coding: utf-8 -*-

from torolib import torolib
import boto3
import hashlib
import json
import logging
import os
import pygame
import random
import redis
import queue
import time

class talk(object):

    def __init__(self):
        # read the configuration
        self.torolib = torolib(redis = None)
        self.config = self.torolib.getJsonContent(fileName='/etc/torobert/talk.config.json')
        # prepare logging
        loggingConfig = self.torolib.prepareLoggingConfiguration(config=self.config.get('logging',{}))
        logging.basicConfig(**loggingConfig)
        logging.info('Starting talk')
        # initialize redis, which is used as an in-memory message broker and as a database for status values
        self.redis = redis.Redis(host=self.config['redis'].get('host','localhost'),port=self.config['redis'].get('port',6379),db=self.config['redis'].get('db',0))
        self.redisPubSub = self.redis.pubsub()
        self.redisPubSub.subscribe('torobert2talk')
        # initialize polly, an amazon web service, used for text to speech synthesis
        self.polly = boto3.Session(aws_access_key_id=self.config['tts']['aws_key_id'],aws_secret_access_key=self.config['tts']['aws_access_key'],region_name='eu-central-1').client('polly')
        # initialize pygame, which is used for playing ogg files generated by polly
        pygame.init()
        pygame.mixer.init()
        self.audio = pygame.mixer.music
        # set up the internal queue, it gets filled with content from messages received via redis
        self.messages = queue.Queue()


    def deleteAudioFiles(self):
        '''delete all audio files of a certain age if their name starts with "temp" (which happens, if the textGenerator marked a message with keepAudioFile=True)'''
        if self.config['sounds'].get('deleteFilesAfter',-1) > -1:
            for file in os.listdir(self.config['tts']['outputFolder']):
                fileFullName = os.path.join(self.config['tts']['outputFolder'], file)
                if os.path.isfile(fileFullName):
                    if (file[:4]=='temp'):
                        fileAge=(time.time()-os.stat(fileFullName).st_mtime)
                        if fileAge > self.config['sounds'].get('deleteFilesAfter',86400):
                            logging.debug(f'deleting old temporary files {file}')
                            os.remove(fileFullName)



    def main(self):
        '''the main loop: process messages and read them'''
        try:
            while True:
                message = self.redisPubSub.get_message()
                if message:
                    self.processMessage(message)
                if self.audio.get_busy()==0 and self.messages.qsize()>0:
                    self.pickMessage()
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info('Talk aborted by user, KeyboardInterrupt')
        except Exception as e:
            logging.error('An error occured, shutting Talk down: ',exc_info=e)
            raise


    def pickMessage(self):
        '''picks a message from the internal messages queue (if not empty) and commits it to the say method'''
        logging.debug('picking message from internal queue (if any)')
        if not self.messages.empty():
            message = self.messages.get()
            self.say(text=message['text'], keepAudioFile=message.get('keepAudioFile',False))


    def processMessage(self, message):
        '''transfer incoming messages into the internal queue, sort them'''
        if message.get('type','')=='message':
            message = json.loads(message.get('data',''))
            message['sort'] = str(message.get('prio',5)).zfill(4)+"_"+str(time.time())
            if message.get('text',None):
                if message.get('abortPriorMessage',False):
                    self.audio.stop()
                    self.messages.queue.clear()
                time.sleep(0.2)
                self.messages.put(message)
                self.sortMessages()


    def say(self, text, volume=None, suffix="", keepAudioFile=False):
        '''turn a text string into a sound file and read it out aloud'''
        logging.debug('say called')
        self.deleteAudioFiles()
        if random.random() < self.config['sounds'].get('prefixChance',0):
            text = self.config['sounds'].get('prefixText','') + text
        if random.random() < self.config['sounds'].get('suffixChance',0):
            text = text + self.config['sounds'].get('suffixText','')
        if len(text) > self.config['tts']['maximumLenghtOfText']:
            logging.warning('A Text has exceeded the maximumLenghtOfText and was shortened.')
            newLen = self.config['tts']['maximumLenghtOfText']-len(suffix)
            text = text[0:newLen] + suffix
        for textToReplace in self.config['tts'].get('textReplacements',{}).keys():
            text = text.replace(textToReplace,self.config['tts'].get('textReplacements',{}).get(textToReplace,textToReplace))
        filename = self.textToSoundfile(text=text, keepAudioFile=keepAudioFile)
        if not volume:
            volume = self.redis.get('volume')
            if volume:
                volume = int(volume)
            else:
                volume = 80
        # workaround: after a few hours, pygame distorts the sound output unless it is reinitialized often
        if self.redis.get('noPygameReinit') != b'1':
            pygame.mixer.quit()
            pygame.mixer.init()
            self.audio = pygame.mixer.music
        # now let's acutally play the audio file
        self.audio.set_volume(volume/100)
        self.audio.load(filename)
        if self.config['sounds']['enabled']==1:
            self.isTalking = True
            self.audio.play()


    def sortMessages(self):
        '''uses bubble sort on the messages in the internal queue, messages are sorted by priority and time of arrival'''
        qsize = self.messages.qsize()
        logging.debug('sorting %s messages' % qsize)
        for i in range(qsize):
            a = self.messages.get()
            for j in range(qsize-1):
                b = self.messages.get()
                if a['sort'] > b['sort'] :
                    self.messages.put(b)
                else:
                    self.messages.put(a)
                    a = b
            self.messages.put(a)


    def textToSoundfile(self, text, voice='Hans', textType='ssml', keepAudioFile=False):
        '''takes a text string as input and converts it to a sound file on disk'''
        logging.info('tts called')
        logging.debug('tts text: ' + text)
        if keepAudioFile == False:
            fileNamePrefix = 'temp'
        else:
            fileNamePrefix = ''
        if not voice:
            voice = self.defaultVoice
        text = text.replace('"',"'").replace(';',',').replace('\n',' ').replace('\r',' ')
        if not textType in ['ssml','text']:
            textType = 'ssml'
        if textType =='ssml' and text[0:27]!='<speak><prosody rate="92%">':
            text='<speak><prosody rate="92%">'+text+'</prosody></speak>'
        filename = voice + text
        filename = filename.encode('utf-8')
        filenameAsHash = hashlib.md5(filename).hexdigest()
        filename = os.path.join(self.config['tts']['outputFolder'],fileNamePrefix+filenameAsHash + '.ogg')
        if not os.path.isfile(filename):
            response = self.polly.synthesize_speech(VoiceId=voice, OutputFormat='ogg_vorbis', Text = text, TextType=textType)
            file = open(filename, 'wb')
            file.write(response['AudioStream'].read())
            file.close()
        return filename


if __name__ == '__main__':
    talk = talk()
    talk.main()
