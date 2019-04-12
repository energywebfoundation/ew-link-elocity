import datetime
import json
import os
import time

import energyweb

from tasks.database.memorydao import MemoryDAOFactory
from tasks.origin import CooProducerTask, CooConsumerTask
from tasks.chargepoint import Ocpp16ServerTask
from tasks.dbsync import ElasticSyncTask


class MyApp(energyweb.dispatcher.App):

    def _handle_exception(self, e: Exception):
        print(f'App failed because {e.with_traceback(e.__traceback__)}\nExiting.')

    def _configure(self):

        def parse_config_file(path):
            if not os.path.isfile(path):
                raise energyweb.config.ConfigurationFileError('Configuration file not found')
            try:
                return json.load(open(path))
            except Exception:
                raise energyweb.config.ConfigurationFileError('Malformed json.')

        def register_ocpp_server():
            interval = datetime.timedelta(minutes=1)
            self._register_queue('ev_charger_command')
            self._register_queue('ev_chargers_available', 1)
            if 'ocpp16-server' not in app_config \
                    or not {'host', 'port'}.issubset(dict(app_config['ocpp16-server']).keys()):
                raise energyweb.config.ConfigurationFileError('Configuration file missing Ocpp 1.6 configuration.')
            host, port = app_config['ocpp16-server']['host'], app_config['ocpp16-server']['port']
            self._register_task(Ocpp16ServerTask(self.queue, MemoryDAOFactory(), interval, host, port))

        def register_origin():
            interval = datetime.timedelta(minutes=2)
            origin_config: energyweb.config.CooV1Configuration = energyweb.config.parse_coo_v1(app_config)
            for producer in origin_config.production:
                self._register_task(CooProducerTask(producer, interval, self.queue, store='/tmp/origin/produce'))
            for consumer in origin_config.consumption:
                self._register_task(CooConsumerTask(consumer, interval, self.queue, store='/tmp/origin/consume'))

        def register_db_sync():
            interval = datetime.timedelta(minutes=1)
            if 'elastic-sync' not in app_config \
                    or not {'service_urls'}.issubset(dict(app_config['elastic-sync']).keys()):
                raise energyweb.config.ConfigurationFileError('Configuration file missing ElasticSync configuration.')
            self._register_task(ElasticSyncTask(self.queue, interval, app_config['elastic-sync']['service_urls']))

        def register_iot_layer():
            pass

        config_path = '/opt/elocity/ew-link.config'

        try:
            while not os.path.exists(config_path):
                print(f'App is waiting for config file')
                time.sleep(3)
        except KeyboardInterrupt:
            self.loop.close()
            quit()
        except Exception as e:
            self.loop.close()
            quit()

        try:
            app_config: dict = parse_config_file(config_path)
            register_ocpp_server()
            register_db_sync()
            register_iot_layer()
            register_origin()
        except energyweb.config.ConfigurationFileError as e:
            print(f'Error in configuration file: {e.with_traceback(e.__traceback__)}\nExiting.')
            self.loop.close()
        except Exception as e:
            self._handle_exception(e)
            self.loop.close()

    def _clean_up(self):
        pass


if __name__ == '__main__':
    MyApp().run()
