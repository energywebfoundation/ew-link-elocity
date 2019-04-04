import datetime
import json
import os

import energyweb

from tasks.database.memorydao import MemoryDAOFactory
from tasks.origin import CooProducerTask, CooConsumerTask
from tasks.chargepoint import Ocpp16ServerTask


class MyApp(energyweb.dispatcher.App):

    def _handle_exception(self, e: Exception):
        print('==== APP ERROR ====')
        print(f'{e.with_traceback(e.__traceback__)}')

    def _configure(self):

        def parse_config_file(path):
            if not os.path.isfile(path):
                raise energyweb.config.ConfigurationFileError('Configuration file not found')
            return json.load(open(path))

        def register_ocpp_server():
            self._register_queue('ev_charger_command')
            self._register_queue('ev_chargers_available', 1)
            if 'ocpp16' not in app_config or not {'host', 'port'}.issubset(dict(app_config['ocpp16']).keys()):
                raise energyweb.config.ConfigurationFileError('Configuration file missing Ocpp 1.6 configuration.')
            host, port = app_config['ocpp16']['host'], app_config['ocpp16']['port']
            self._register_task(Ocpp16ServerTask(self.queue, MemoryDAOFactory(), host, port))

        def register_origin():
            interval = datetime.timedelta(minutes=2)
            origin_config: energyweb.config.CooV1Configuration = energyweb.config.parse_coo_v1(app_config)
            for producer in origin_config.production:
                self._register_task(CooProducerTask(producer, interval, self.queue, store='/tmp/origin/produce'))
            for consumer in origin_config.consumption:
                self._register_task(CooConsumerTask(consumer, interval, self.queue, store='/tmp/origin/consume'))
        try:
            app_config: dict = parse_config_file('/opt/ew-link.config')
            register_ocpp_server()
            register_origin()
        except energyweb.config.ConfigurationFileError as e:
            print(f'Error in configuration file: {e.with_traceback(e.__traceback__)}')
        except Exception as e:
            print(f'Fatal error: {e}')

    def _clean_up(self):
        pass


if __name__ == '__main__':
    MyApp().run()
