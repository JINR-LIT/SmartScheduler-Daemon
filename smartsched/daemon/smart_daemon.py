#!/usr/bin/env python3

import importlib.machinery
import configparser
from . import base_daemon
from . import base_strategy

from multiprocessing import Process
import signal
import time
import sys
import logging


CONFIG_PATH = '/etc/smartscheduler/config.cfg'


class SmartDaemon(base_daemon.BaseDaemon):

    counter = 0
    shutdown = False
    # config_path = '/etc/smartscheduler/config.cfg'

    def __init__(self, pidfile='/tmp/smartscheduler.pid', stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        base_daemon.BaseDaemon.__init__(self, pidfile)

        config = configparser.RawConfigParser()
        config.read(CONFIG_PATH)
        self.config = dict(config.items('daemon'))

        signal.signal(signal.SIGINT, self.do_shutdown)
        signal.signal(signal.SIGTERM, self.do_shutdown)

    def do_shutdown(self, one, two):
        self.logger.info("Signal came to master")
        self.logger.info(str(one))
        self.logger.info(str(two))
        self.shutdown = True

    def run(self):        
        strategy = importlib.machinery.SourceFileLoader('strategy', self.config['strategy_path']).load_module()
        strategy_runner = base_strategy.create_strategy_runner(strategy.target_class, self.config)

        self.logger = logging.getLogger('master')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler('/root/master.log')
        self.logger.addHandler(fh)

        self.logger.info("Master is running")

        process = Process(target=strategy_runner)
        self.logger.info("Starting slave")
        process.start()
        isRunning = True
        self.logger.info('Initiate slave monitoring')
        while isRunning:

            self.logger.info(str(self.counter) + ': Master message')
            self.counter += 1
            time.sleep(5)
            if self.shutdown:
                self.logger.info('Master: About shutdown')
                process.terminate()
                isRunning = False
                


if __name__ == "__main__":
    x = SmartDaemon('/tmp/daemon-example.pid')
    x.run()
