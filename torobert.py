# -*- coding: utf-8 -*-

from flask import Flask, url_for, render_template, request, json, send_from_directory
from shell_command import shell_output
from threading import Thread
import datetime
import getpass
import importlib
import json
import logging
import os
import redis
import sys
import time
import torolib


class torobert(object):

    def __init__(self):
        # read the configuration from json file
        self.torolib = torolib.torolib(redis = None)
        self.config = self.torolib.getJsonContent(fileName='/etc/torobert/torobert.config.json')
        # initialize logging
        loggingConfig = self.torolib.prepareLoggingConfiguration(config=self.config.get('logging',{}))
        logging.basicConfig(**loggingConfig)
        logging.info('Starting Torobert')
        # check if run as root
        user = getpass.getuser()
        if user=='root':
            # running torobert as root is generally a bad idea, especially because of the dynamic module loading
            logging.error('torobert was started as root, aborting')
            sys.exit('torobert may not be started as root')
        # initialize redis, which is used as an in-memory message broker and as a database for status values
        self.redis = redis.Redis(host=self.config['redis'].get('host','localhost'),port=self.config['redis'].get('port',6379),db=self.config['redis'].get('db',0))
        self.redisPubSub = self.redis.pubsub()
        self.redisPubSub.subscribe('webApp2torobert')
        # import and instanciate textGenerator extensions if enabled in the config file
        # also: fill the recurrences list which is used to schedule calling the extensions
        self.recurrences = []
        self.textGenerators = {}
        for textGeneratorName in self.config['textGenerators'].keys():
            if self.config['textGenerators'][textGeneratorName].get('enabled',0)==1:
                sys.path.insert(0,'./textGenerators/'+textGeneratorName)
                logging.info(f'importing textGenerator {textGeneratorName}')
                extLib = importlib.import_module(textGeneratorName)
                self.textGenerators[textGeneratorName] = extLib.textGenerator(redis=self.redis)
                if 'getWebAppConfig' in dir(self.textGenerators[textGeneratorName]):
                    self.config['textGenerators'][textGeneratorName]['webApp'] = self.textGenerators[textGeneratorName].getWebAppConfig()
                recurrence = self.config['textGenerators'][textGeneratorName].get('recurrence',None)
                if recurrence:
                    if recurrence > 0:
                        initialDelay = self.config['textGenerators'][textGeneratorName].get('initialDelay',None)
                        if not initialDelay:
                            initialDelay = random.randint(60,600)
                        self.recurrences.append({'name':textGeneratorName,'recurrence':recurrence, 'nextExecution': time.time() + initialDelay,'type':'textGenerator'})
        # add system recurrences which are independent from the text generators
        for recurrenceFuncName in self.config['systemRecurrences'].keys():
            if self.config['systemRecurrences'][recurrenceFuncName].get('enabled',0)==1:
                recurrence = self.config['systemRecurrences'][recurrenceFuncName].get('recurrence',None)
                if recurrence > 0:
                    initialDelay = self.config['systemRecurrences'][recurrenceFuncName].get('initialDelay',None)
                    if not initialDelay:
                        initialDelay = random.randint(60,600)
                    self.recurrences.append({'name':recurrenceFuncName,'recurrence':recurrence, 'nextExecution': time.time() + initialDelay,'type':'systemRecurrence'})
        # start the webApp
        webAppThread = Thread(target = self.webApp, args =( ), daemon = True)
        webAppThread.start()
        # give an intro speech if torobert is started for the first time
        if self.redis.get('hasBeenUsed') != b'1':
            message=self.textGenerators['system'].getMessageByTags(['introTextFirstTimeOn','online'])
            if message:
                self.redis.publish('torobert2talk',json.dumps(message))
            self.torolib.factoryReset(self.redis)
        # read the init texts of the text generators if applicable
        for textGeneratorName in self.textGenerators.keys():
            if 'getMessageOnInit' in dir(self.textGenerators[textGeneratorName]):
                message=self.textGenerators[textGeneratorName].getMessageOnInit()
                if message:
                    self.redis.publish('torobert2talk',json.dumps(message))


    def callTextGenerator(self, textGeneratorName, variables={}, abortPriorMessage=False, calledBy=''):
        '''gathers a bunch of variables, calls a given textGenerator to get a message and then places that message in the talk queue'''
        # get a message from the textGenerator (if it actually returns one) and put it in the message queue
        try:
            message = self.textGenerators[textGeneratorName].getMessageOnRecurrence(variables=variables, calledBy=calledBy)
        except Exception as e:
            logging.error(f'An error occured while executing the textGenerator {textGeneratorName}: ',exc_info=e)
            message = None
        if message:
            message['abortPriorMessage'] = abortPriorMessage
            self.redis.publish('torobert2talk',json.dumps(message))
        else:
            logging.debug(f'no message found by the textGenerator {textGeneratorName}.')


    def cleanup(self):
        '''perform all cleanup operations like closing connections etc, also call cleanup operations from textGenerators'''
        for textGeneratorName in self.textGenerators.keys():
            if 'cleanup' in dir(self.textGenerators[textGeneratorName]):
                self.textGenerators[textGeneratorName].cleanup()


    def getCpuTemperature(self):
        '''get cpu temperature using vcgencmd'''
        try:
            output = shell_output("vcgencmd measure_temp")
            return float(output[output.index('=') + 1:output.rindex("'")])
        except Exception as e:
            logging.warning('error while calling vcgencmd, this is to be expected on non-raspberry-pis, error message:',exc_info=e)


    def getVariableValues(self, noMotionSince=-1):
        '''create the variables dict, which is used in conditions in some of the texts of the textGenerators'''
        variables = {}
        now = datetime.datetime.now()
        variables['DAY'] = now.strftime('%m%d')
        variables['MONTH'] = int(now.strftime('%m'))
        variables['HOUR'] = int(now.strftime('%H'))
        variables['MINUTE'] = int(now.strftime('%M'))
        variables['DAYOFWEEK'] = int(now.strftime('%w'))
        variables['NOMOTIONSINCE'] = noMotionSince
        return variables


    def logStatus(self, me):
        '''writes a log entry with system status info - for now only including cpu temperature'''
        cpuTemp = self.getCpuTemperature()
        logging.info(f"CPU Temperature at {cpuTemp}")


    def main(self):
        try:
            motionDetected = None
            noMotionSince = -1
            while True:
                # check if the motion sensor senses motion. If the motion ceases, save the timestamp of that event (used for some textGenerator conditions)
                motionDetectedOldValue = motionDetected
                motionDetected = False
                if self.redis.hget('sensors','mockMotion') == b'1':
                    motionDetected = True
                else:
                    if self.redis.hget('sensors','motion') == b'1':
                        #print (float(self.redis.hget('sensors','motionLastDetection').decode('ascii')))
                        motionDetected = True
                if motionDetected == False and motionDetectedOldValue == True:
                    self.redis.hset('sensors','motionNoLongerDetected',time.time())
                    variables = self.getVariableValues(noMotionSince=0)
                elif motionDetected == True and motionDetectedOldValue == False:
                    motionNoLongerDetected = self.redis.hget('sensors','motionNoLongerDetected')
                    if motionNoLongerDetected:
                        noMotionSince = time.time() - float(motionNoLongerDetected)
                    else:
                        noMotionSince = -1
                    variables = self.getVariableValues(noMotionSince=noMotionSince)
                    # process greeting messages after a longer absence
                    greetingAfterAbsence = self.config.get('greetingAfterAbsence',10800)
                    if (noMotionSince > greetingAfterAbsence and greetingAfterAbsence > -1 and motionDetected):
                        for textGeneratorName in self.textGenerators.keys():
                            if 'getMessageOnReactivation' in dir(self.textGenerators[textGeneratorName]):
                                message=self.textGenerators[textGeneratorName].getMessageOnReactivation(variables=variables)
                                if message:
                                    self.redis.publish('torobert2talk',json.dumps(message))
                else:
                    variables = self.getVariableValues(noMotionSince=noMotionSince)
                # process recurring tasks
                for recurrence in self.recurrences:
                    if time.time() > recurrence['nextExecution']:
                        if recurrence['type'] == 'textGenerator':
                            if motionDetected:
                                if self.redis.get('talkingInitiative')==b'1':
                                    self.callTextGenerator(textGeneratorName=recurrence['name'],variables=variables, calledBy='recurrence')
                                else:
                                    logging.debug('textGenerator %s not triggered due to a lack of initative' % recurrence['name'])
                            else:
                                logging.debug('textGenerator %s not called because no motion has been detected' % recurrence['name'])
                        elif recurrence['type'] == 'systemRecurrence':
                            try:
                                func = getattr(self, recurrence['name'])
                            except AttributeError:
                                log.error (f"function '{recurrence['name']}' does not exist but it is listed as a systemRecurrence in the config.")
                            else:
                                callFunction = getattr(self, recurrence['name'])
                                callFunction(self)
                        recurrence['nextExecution'] = time.time() + recurrence['recurrence']
                # react to changes in the webApp
                message = self.redisPubSub.get_message()
                if message:
                    if message.get('type','')=='message':
                        message = json.loads(message.get('data',''))
                        if message.get('action') == 'onDemand':
                            self.callTextGenerator(textGeneratorName=message['textGeneratorName'], variables=variables, abortPriorMessage=True, calledBy='webApp')
                time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info('closing Torobert, KeyboardInterrupt')
            self.cleanup()
        except Exception as e:
            logging.error('An Error occured, shutting Torobert down: ',exc_info=e)
            raise


    def webApp(self):
        self.app = Flask('webApp')
        meta = {'title': self.config['nameWritten']}
        @self.app.route('/')
        def wcOnDemand():
            cards = []
            textGenerators = self.config['textGenerators']
            i = 0
            for textGeneratorName in textGenerators.keys():
                if 'webApp' in textGenerators[textGeneratorName].keys():
                    if textGenerators[textGeneratorName]['webApp'].get('onDemand',0)==1:
                        i += 1
                        if i > 5:
                            i = 1
                        cards.append({ \
                            'name': textGeneratorName, \
                            'heading': textGenerators[textGeneratorName]['webApp'].get('heading',textGeneratorName), \
                            'fontAwesomeIcon': textGenerators[textGeneratorName]['webApp'].get('fontAwesomeIcon','fas fa-question')+' cs%s' % i})
            return render_template('onDemand.html', cards=cards, meta=meta)
        @self.app.route('/settings/')
        def wcSettings():
            volume = self.redis.get('volume')
            if volume:
                volume = int(volume)
            else:
                volume = 75
            settings = {'volume':volume}
            if self.redis.get('remoteSSH')==b"1":
                settings['remoteSSH'] = True
            else:
                settings['remoteSSH'] = False
            if self.redis.get('talkingInitiative')==b"1":
                settings['talkingInitiative'] = True
            else:
                settings['talkingInitiative'] = False
            return render_template('settings.html', meta=meta, settings=settings)
        @self.app.route('/onDemandAction', methods=['POST'])
        def onDemandAction():
            self.redis.publish('webApp2torobert',json.dumps({'action':'onDemand', 'textGeneratorName':request.form['textGeneratorName']}))
            return json.dumps({'status':'OK','textGeneratorName':request.form['textGeneratorName']});
        @self.app.route('/onToggleRemoteSSH', methods=['POST'])
        def onToggleRemoteSSH():
            if request.form['RemoteSSH']=='true':
                logging.info('activating remoteSSH due to webApp action')
                self.redis.set('remoteSSH',1)
            else:
                logging.info('deactivating remoteSSH due to webApp action')
                self.redis.set('remoteSSH',0)
            return json.dumps({'status':'OK','RemoteSSH':request.form['RemoteSSH']});
        @self.app.route('/onToggleInitiative', methods=['POST'])
        def onToggleInitiative():
            if request.form['talkingInitiative']=='true':
                logging.info('activating talkingInitiative due to webApp action')
                self.redis.set('talkingInitiative',1)
            else:
                logging.info('deactivating talkingInitiative due to webApp action')
                self.redis.set('talkingInitiative',0)
            return json.dumps({'status':'OK','talkingInitiative':request.form['talkingInitiative']});
        @self.app.route('/onSetVolume', methods=['POST'])
        def onSetVolume():
            volume = int(request.form['volume'])
            if volume>=0 and volume <= 100:
                self.redis.set('volume',volume)
            return json.dumps({'status':'OK','RemoteSSH':volume});
        @self.app.route('/favicon.ico')
        def favicon():
            return send_from_directory(os.path.join(self.app.root_path, 'static'),'favicon.ico', mimetype='image/vnd.microsoft.icon')
        self.app.run(host="0.0.0.0")


if __name__ == '__main__':
    torobert = torobert()
    torobert.main()
