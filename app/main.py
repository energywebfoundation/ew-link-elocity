import datetime
import json
import os

import energyweb

from tasks.ocpp16.memorydao import MemoryDAOFactory
from tasks.origin import CooProducerTask, CooConsumerTask
from tasks.ev_charger import Ocpp16ServerTask


class MyApp(energyweb.dispatcher.App):

    def _handle_exception(self, e: Exception):
        print('==== APP ERROR ====')
        print(f'{e.with_traceback(e.__traceback__)}')

    def _clean_up(self):
        pass

    def _parse_config_file(self, path):
        if not os.path.isfile(path):
            raise energyweb.config.ConfigurationFileError('Configuration file not found')
        app_configuration_file = json.load(open(path))
        return energyweb.config.parse_coo_v1(app_configuration_file)

    def _register_ocpp_server(self, config):
        self._register_queue('ev_charger_command')
        self._register_queue('ev_chargers_available', 1)
        self._register_task(Ocpp16ServerTask(self.queue, MemoryDAOFactory(), 'localhost', 8080))

    def _register_origin(self, config):
        interval = datetime.timedelta(minutes=5)
        for producer in config.production:
            self._register_task(
                CooProducerTask(task_config=producer, polling_interval=interval, store='/tmp/origin/produce'))
        for consumer in config.consumption:
            self._register_task(
                CooConsumerTask(task_config=consumer, polling_interval=interval, store='/tmp/origin/consume'))

    def _configure(self):
        try:
            config = None
            self._register_ocpp_server(None)
        except energyweb.config.ConfigurationFileError as e:
            print(f'Error in configuration file: {e}')
        except Exception as e:
            print(f'Fatal error: {e}')


if __name__ == '__main__':
    MyApp().run()
