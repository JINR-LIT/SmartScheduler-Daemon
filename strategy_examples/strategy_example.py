import signal
import logging
import time
import smartsched.daemon.base_strategy as base_strategy



class mock_runner(base_strategy.BaseStrategy):
    counter = 0

    def __init__(self, config):
        base_strategy.BaseStrategy.__init__(self, config)
        self.sleep_time = int(config['sleep_time'])
        self.logger = logging.getLogger('slave')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler('/root/slave.log')
        self.logger.addHandler(fh)

    def perform_strategy(self):
        self.logger.info(str(self.counter) + ": This could be something useful")
        self.counter += 1

    def before_shutdown(self):
        self.logger.info('Before shutdown')

target_class = mock_runner
