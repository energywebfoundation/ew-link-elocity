import datetime
import json

import energyweb

from app.tasks.origin import CooProducerTask, CooConsumerTask
from app.tasks.ev_charger import EvChargingStationControlTask




class MyApp(energyweb.dispatcher.App):

    def configure(self):
        try:
            app_configuration_file = json.load(open('config.json'))
            app_config = energyweb.config.parse_coo_v1(app_configuration_file)
            interval = datetime.timedelta(seconds=3)
            for producer in app_config.production:
                self.add_task(CooProducerTask(task_config=producer, polling_interval=interval, store='/tmp/origin/produce'))
            for consumer in app_config.consumption:
                self.add_task(CooConsumerTask(task_config=consumer, polling_interval=interval, store='/tmp/origin/consume'))
            self.add_task(EvChargingStationControlTask(interval))
        except energyweb.config.ConfigurationFileError as e:
            print(f'Error in configuration file: {e}')
        except Exception as e:
            print(f'Fatal error: {e}')


if __name__ == '__main__':
    MyApp().run()
