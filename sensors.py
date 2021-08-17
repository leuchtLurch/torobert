# -*- coding: utf-8 -*-

import json
import logging
import redis
import serial
import time
import torolib

class sensors(object):

    def __init__(self):
        # read the configuration from json file
        self.torolib = torolib.torolib(redis = None)
        self.config = self.torolib.getJsonContent(fileName='/etc/torobert/sensors.config.json')
        # initialize logging
        loggingConfig = self.torolib.prepareLoggingConfiguration(config=self.config.get('logging',{}))
        logging.basicConfig(**loggingConfig)
        logging.info('Starting Torobert\'s sensor data monitoring...')
        # initialize redis, which is used as an in-memory message broker and as a database for status values
        self.redis = redis.Redis(host=self.config['redis'].get('host','localhost'),port=self.config['redis'].get('port',6379),db=self.config['redis'].get('db',0))
        # serial connection to the USB-connected ESP32 module, bearing sensors
        try:
            self.serialConnEsp32 =serial.Serial(self.config['esp32']['device'],self.config['esp32']['speed'], timeout=1)
        except serial.serialutil.SerialException:
            self.serialConnEsp32 = False
            logging.warning('no attached sensor module detected')


    def main(self):
        try:
            if self.serialConnEsp32:
                while True:
                    result = {}
                    try:
                        esp32line = self.serialConnEsp32.readline().decode('ascii')
                        result = json.loads(esp32line)
                    except json.decoder.JSONDecodeError:
                        pass
                    except UnicodeDecodeError:
                        pass
                    except Exception as e:
                        logging.error('An error occured, shutting sensors.py down: ',exc_info=e)
                        raise
                    logging.debug(f"sending result {result}")
                    self.redis.hset('sensors','motion',result.get('motion',-1))
                    self.redis.hset('sensors','motionLastDetection',time.time())
        except KeyboardInterrupt:
            logging.info('Closing Torobert\'s sensor data monitoring, KeyboardInterrupt...')
        except Exception as e:
            logging.error('An error occured, shutting sensors.py down: ',exc_info=e)
            raise


if __name__ == '__main__':
    sensors = sensors()
    sensors.main()
