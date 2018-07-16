#!/usr/bin/env python3

import importlib.machinery
import configparser
import signal
import sys
import time
import logging

from multiprocessing import Process

from . import base_daemon
from . import base_strategy
from smartsched.common import StreamToLogger

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

        handler = logging.FileHandler(self.config['log_filename'])
        self.logger = logging.getLogger(self.config['log_name'])
        self.logger.setLevel(logging.getLevelName(self.config['log_level']))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        sl = StreamToLogger(self.logger, logging.ERROR)
        sys.stderr = sl

        signal.signal(signal.SIGINT, self.do_shutdown)
        signal.signal(signal.SIGTERM, self.do_shutdown)

    def do_shutdown(self, one, two):
        self.logger.info("Shutdown signal came to master")
        self.shutdown = True

    def run(self):
        self.logger.info('SmartDaemon Master process init - Susscess')

        self.start_time = time.time()
        self.processes = {}
        strategy_list = self.config['strategies'].split(',')
        self.logger.info('Strategies found: ' + str(strategy_list))
        for strategy_name in strategy_list:
            strategy_config_parser = configparser.RawConfigParser()
            strategy_config_parser.read(CONFIG_PATH)
            strategy_config = dict(strategy_config_parser.items(strategy_name))

            #strategy = importlib.machinery.SourceFileLoader('strategy', self.config['strategy_path']).load_module()
            strategy_module = importlib.machinery.SourceFileLoader(strategy_name, strategy_config['strategy_path']).load_module()
            strategy_runner = base_strategy.create_strategy_runner(strategy_module.target_class, strategy_config)
            self.processes[strategy_name] = Process(target=strategy_runner)

        for strategy, process in self.processes.items():
            process.start()
            self.logger.info(strategy + ' started')

        isRunning = True
        while isRunning:
            self.counter += 1
            current_time = time.time() - self.start_time
            for strategy, process in self.processes.items():
                message = "{0:.6f}".format(current_time) + ': (Health Check) ' + strategy + ' process is '
                if process.is_alive():
                    self.logger.info(message + 'OK')
                else:
                    self.logger.info(message + 'DEAD')

            time.sleep(5)
            if self.shutdown:
                self.logger.info('Master: About to shutdown')
                for strategy, process in self.processes.items():
                    self.logger.info('Terminating ' + strategy + ' process')
                    process.terminate()
                isRunning = False

if __name__ == "__main__":
    x = SmartDaemon('/tmp/daemon-example.pid')
    x.run()
