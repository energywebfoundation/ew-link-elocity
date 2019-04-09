import asyncio
import calendar
import datetime

import energyweb

from tasks.database.dao import DAOFactory
from tasks.database.elasticdao import ElasticSearchDAOFactory, ElasticSearchDAO
from tasks.ocpp16.protocol import ChargingStation, Ocpp16
from tasks.ocpp16.server import Ocpp16Server


class EVchargerEnergyMeter(energyweb.EnergyDevice):

    def __init__(self, service_urls: tuple, manufacturer, model, serial_number, energy_unit, is_accumulated,
                 connector_id: int, latitude=None, longitude=None):
        self.service_urls = service_urls
        self.connector_id = connector_id
        super().__init__(manufacturer, model, serial_number, energy_unit, is_accumulated, latitude, longitude)

    def read_state(self, *args, **kwargs) -> energyweb.EnergyData:
        els_tx_dao: ElasticSearchDAO = ElasticSearchDAOFactory('transactions', *self.service_urls).\
            get_instance(ChargingStation.Transaction)
        results = els_tx_dao.query({"bool": {
            "must_not": {"exists": {"field": 'co2_saved'}},
            "must": [{"exists": {"field": 'meter_start'}},
                     {"exists": {"field": 'meter_stop'}},
                     {"match": {"cs_reg_id": self.serial_number}},
                     {"match": {"connector_id": self.connector_id}}]
        }})
        now = datetime.datetime.now().astimezone()
        results.sort(key=lambda cs: cs.time_start, reverse=True)
        tx: Ocpp16.Transaction = results.pop()
        tx.co2_saved = int(tx.meter_stop) - int(tx.meter_start)
        energy_data = {
            "device": self,
            "access_epoch": calendar.timegm(now.timetuple()),
            "raw": tx.to_dict(),
            "energy": tx.co2_saved,
            "measurement_epoch": calendar.timegm(tx.time_stop.timetuple())
        }
        els_tx_dao.update(tx)
        return energyweb.EnergyData(**energy_data)

    def write_state(self, *args, **kwargs) -> energyweb.EnergyData:
        pass


class Ocpp16ServerTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, factory: DAOFactory, retry_interval: datetime.timedelta, host: str, port: int):
        """ Use different DAOs to change storage services """
        self._queue = queue
        self._factory = factory
        self.server_address = (host, port)
        self._future = None
        energyweb.Task.__init__(self, queue, polling_interval=retry_interval, eager=True, run_forever=True)
        energyweb.Logger.__init__(self, 'Ocpp16Server')

    class Ocpp16ServerLogger(Ocpp16Server):

        def __init__(self, factory, queue, console):
            self.console = console
            super().__init__(factory, queue)

        def _message_handler(self, msg):
            self.console.debug(f'{msg.serialize()}')

        def _error_handler(self, text, e):
            self.console.error(f'{text}{e.with_traceback(e.__traceback__)}')

    async def _prepare(self):
        if not {'ev_charger_command', 'ev_chargers_available'}.issubset(self._queue.keys()):
            raise AssertionError("Please register queues 'ev_charger_command' and 'ev_chargers_available' on the app.")
        server = self.Ocpp16ServerLogger(self._factory, self._queue, self.console)
        self._future = server.get_server_future(*self.server_address)
        self.console.info(f'Server running on http://{self.server_address[0]}:{self.server_address[1]}')

    def _handle_exception(self, e: Exception):
        self.console.error(f'Ocpp16 Server failed because {e.with_traceback(e.__traceback__)}')

    async def _main(self):
        await self._future

    async def _finish(self):
        try:
            self.console.info('Awaiting to run task again.')
            await asyncio.sleep(self.polling_interval.total_seconds())
            self._future.ws_server.close()
        except Exception as e:
            self._handle_exception(e)
