#!/usr/bin/env python3

import signal
import time
import logging


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
