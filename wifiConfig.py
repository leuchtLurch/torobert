# -*- coding: utf-8 -*-
from shell_command import shell_output
import datetime
import importlib
import json
import logging
import os
import pygame
import re
import redis
import sys
import time
import torolib
import urllib.request


class wifiConfig(object):

    def __init__(self):
        # read the configuration from json file
        self.torolib = torolib.torolib(redis = None)
        self.config = self.torolib.getJsonContent(fileName='/etc/torobert/torobert.config.json')
        # initialize logging
        loggingConfig = self.torolib.prepareLoggingConfiguration(config=self.config.get('logging',{}))
        logging.basicConfig(**loggingConfig)
        logging.info('Starting Toroberts wifiConfig')
        # initialize redis, which is used as an in-memory message broker and as a database for status values
        self.redis = redis.Redis(host=self.config['redis'].get('host','localhost'),port=self.config['redis'].get('port',6379),db=self.config['redis'].get('db',0))
        self.redisPubSub = self.redis.pubsub()
        # initialize pygame for sound output
        pygame.init()
        pygame.mixer.init()
        self.audio = pygame.mixer.music


    def main(self):
        if self.redis.get('hasBeenUsed') != b'1':
            self.say(filename='./soundfiles/introTextFirstTimeOn.ogg')
            time.sleep(40)
            self.torolib.factoryReset(self.redis)
        else:
            drivesFound = 0
            # detect all potentially relevant drives
            driveInfos = shell_output("lsblk --output UUID,MOUNTPOINT,LABEL,NAME -l")
            for driveInfo in driveInfos.split('\n'):
                # this looks for drives which have names that start with "sd", for example "sda1"
                match = re.search(r"([\d\w_\-]+)\s+([\d\w\/_\-]*)\s+([\d\w]*)\s+(sd[a-z\d]+)",driveInfo)
                if match:
                    # a potentially relevant drive has been found
                    driveUuid = match.groups()[0]
                    driveMountpoint = match.groups()[1]
                    driveLabel = match.groups()[2]
                    driveName = match.groups()[3]
                    driveMountedByProgram = False
                    drivesFound += 1
                    # mount the drive if it isnt already mounted
                    if driveMountpoint=='':
                        path = '/media/torobert_'+driveUuid
                        logging.debug(f"mounting {path}")
                        if not os.path.isdir(path):
                            os.mkdir(path)
                        if not os.listdir(path):
                            try:
                                mountResult = shell_output(f"mount --uuid {driveUuid} {path}")
                            except:
                                mountResult = 'ERROR'
                            if mountResult == '':
                                driveMountpoint = path
                                driveMountedByProgram = True
                            else:
                                self.say(filename='./soundfiles/errorWifiWhileMounting.ogg')
                                logging.error(f"Some error occured while mounting the device {driveUuid} to {path}: {mountResult}")
                        else:
                            logging.error(f"cannot mount USB device, because {path} is not empty")
                    # open the wifi.txt on the drive
                    if driveMountpoint!='':
                        fileName = os.path.join(driveMountpoint,'wifi.txt')
                        logging.debug(f"trying to read {fileName}")
                        if os.path.isfile(fileName):
                            with open(fileName, 'r') as fh:
                                fileContent = fh.read().split('\n')
                                if len(fileContent)>=2:
                                    ssid = fileContent[0]
                                    password = fileContent[1]
                                    wifiResult = shell_output(f"nmcli dev wifi connect \"{ssid}\" password \"{password}\"")
                                    try:
                                        urllib.request.urlopen('https://www.google.com')
                                        logging.info('A wifi connection has been successfully created!')
                                        self.say(filename='./soundfiles/successWifiConnected.ogg')
                                    except:
                                        logging.error(f"Connecting to wifi was not successful: {wifiResult}")
                                        self.say(filename='./soundfiles/errorWifiNoConnection.ogg')
                                else:
                                    self.say(filename='./soundfiles/errorWifiInvalidFile.ogg')
                                    logging.error("The content of {fileName} seems to be invalid: too few lines")
                        else:
                            self.say(filename='./soundfiles/errorWifiNoFile.ogg')
                            logging.warning(f"The file {fileName} could not be found.")
                    # if the drive was mounted by this program, unmount it now
                    if driveMountedByProgram:
                        logging.debug(f"unmounting {driveMountpoint}")
                        unmountResult = shell_output(f"umount {driveMountpoint}")
                        if unmountResult != '':
                            logging.error(f"Some error occured while unmounting {driveMountpoint}: {mountResult}")
            if drivesFound==0:
                self.say(filename='./soundfiles/errorWifiNoDrive.ogg')
                logging.warning(f"No relevant USB drive could be found")


    def say(self, filename):
        '''reads a system message from the system text extension out aloud'''
        logging.debug(f"say called with {filename}")
        if os.path.isfile(filename):
            pygame.mixer.quit()
            pygame.mixer.init()
            self.audio = pygame.mixer.music
            self.audio.set_volume(1)
            self.audio.load(filename)
            self.audio.play()
            time.sleep(50)
        else:
            logging.error(f"say has been called with the invalid filename '{filename}'.")



if __name__ == '__main__':
    wc = wifiConfig()
    wc.main()
