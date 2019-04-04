import datetime
import json
import os

import energyweb

from tasks.ocpp16.memorydao import MemoryDAOFactory
from tasks.origin import CooProducerTask, CooConsumerTask
from tasks.chargepoint import Ocpp16ServerTask


class MyApp(energyweb.dispatcher.App):

    @staticmethod
    def _parse_config_file(path):
        if not os.path.isfile(path):
            raise energyweb.config.ConfigurationFileError('Configuration file not found')
        return json.load(open(path))

    def _handle_exception(self, e: Exception):
        print('==== APP ERROR ====')
        print(f'{e.with_traceback(e.__traceback__)}')

    def _register_ocpp_server(self, config: dict):
        self._register_queue('ev_charger_command')
        self._register_queue('ev_chargers_available', 1)
        if 'ocpp16' not in config or not {'host', 'port'}.issubset(dict(config['ocpp16']).keys()):
            raise energyweb.config.ConfigurationFileError('Configuration file missing Ocpp 1.6 configuration.')
        host, port = config['ocpp16']['host'], config['ocpp16']['port']
        self._register_task(Ocpp16ServerTask(self.queue, MemoryDAOFactory(), host, port))

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
            app_configuration_file = self._parse_config_file('/opt/ew-link.config')
            # origin_config = energyweb.config.parse_coo_v1(app_configuration_file)
            self._register_ocpp_server(app_configuration_file)
        except energyweb.config.ConfigurationFileError as e:
            print(f'Error in configuration file: {e}')
        except Exception as e:
            print(f'Fatal error: {e}')

    def _clean_up(self):
        pass


if __name__ == '__main__':
    MyApp().run()
