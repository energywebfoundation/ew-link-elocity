import datetime

import energyweb

from tasks.ocpp16.ws_server import server


class EvChargingStationControlTask(energyweb.Task):
    # TODO: Change task run loop is wrong

    def __init__(self, polling_interval: datetime.timedelta):
        energyweb.Task.__init__(self, polling_interval=polling_interval, eager=False)

    def prepare(self):
        print(f'Ocpp 1.6 Server started')

    def run(self, *args):
        return server

    def finish(self):
        server.ws_server.close()
        print('Server stopped')
