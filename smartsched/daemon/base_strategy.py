#!/usr/bin/env python3

import signal
import time
import logging
import sys


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        for line in self.linebuf.splitlines():
            self.logger.log(self.log_level, line.rstrip())

def create_strategy_runner(strategy, config_dict):
    def run_strategy():
        runner = strategy(config_dict)
        runner.run()
    return run_strategy

class BaseStrategy:
    isRunning = False
    logger = None
    sleep_time = 10
    shutdown = False

    def __init__(self, config_dict):
        self.config = config_dict

        signal.signal(signal.SIGINT, self.do_shutdown)
        signal.signal(signal.SIGTERM, self.do_shutdown)

        self.sleep_time = int(self.config['sleep_time'])

        handler = logging.FileHandler(self.config['log_filename'])
        self.logger = logging.getLogger(self.config['log_name'])
        self.logger.setLevel(logging.getLevelName(self.config['log_level']))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        sl = StreamToLogger(self.logger, logging.INFO)
        sys.stdout = sl

        sl = StreamToLogger(self.logger, logging.ERROR)
        sys.stderr = sl


    def do_shutdown(self, signalnum, handler):
        if self.logger:
            self.logger.info('Shutdown signar received')
        self.shutdown = True


    def run(self):
        isRunning = True
        while isRunning:
            self.perform_strategy()
            time.sleep(self.sleep_time)
            if self.shutdown:
                if self.logger:
                    self.logger.info('Initiate shutdown procedure')
                self.before_shutdown()
                isRunning = False

    def perform_strategy(self):
        pass

    def before_shutdown(self):
        pass
