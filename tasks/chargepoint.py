import asyncio
import calendar
import datetime

import energyweb

from tasks.database.dao import DAOFactory
from tasks.database.elasticdao import ElasticSearchDAOFactory, ElasticSearchDAO
from tasks.database.memorydao import MemoryDAOFactory, MemoryDAO
from tasks.ocpp16.protocol import ChargingStation
from tasks.ocpp16.server import Ocpp16Server


class EVchargerEnergyMeter(energyweb.EnergyDevice):

    def __init__(self, service_urls: tuple, manufacturer, model, serial_number, energy_unit, is_accumulated,
                 latitude=None, longitude=None):
        self.service_urls = service_urls
        super().__init__(manufacturer, model, serial_number, energy_unit, is_accumulated, latitude, longitude)

    def read_state(self, *args, **kwargs) -> energyweb.EnergyData:
        els_dao: ElasticSearchDAO = ElasticSearchDAOFactory('elocity', *self.service_urls).get_instance(ChargingStation)
        results = els_dao.retrieve_all()
        results_a = els_dao.query({"bool": {
            "must_not": {"exists": {"field": 'co2_saved'}},
            "must": [{"exists": {"field": 'meter_start'}}, {"exists": {"field": 'meter_stop'}}]
        }})
        results_b = els_dao.query({"bool": {
            "must": [{"exists": {"field": 'meter_start'}}, {"exists": {"field": 'meter_stop'}}]
        }})
        now = datetime.datetime.now().astimezone()
        return energyweb.EnergyData(device=self, access_epoch=calendar.timegm(now.timetuple()), raw='',
                                      energy='', measurement_epoch='')

    def write_state(self, *args, **kwargs) -> energyweb.EnergyData:
        pass


class Ocpp16ServerTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, factory: DAOFactory, host: str, port: int):
        """ Use different DAOs to change storage services """
        self._queue = queue
        self._factory = factory
        self.server_address = (host, port)
        self._future = None
        energyweb.Task.__init__(self, queue, polling_interval=datetime.timedelta(minutes=5), eager=True,
                                run_forever=True)
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
            await asyncio.sleep(60)
            self._future.ws_server.close()
        except Exception as e:
            self._handle_exception(e)


class ElasticSync(energyweb.Task):

    def __init__(self, queue: dict, interval: datetime.timedelta, service_urls: tuple):
        self.service_urls = service_urls
        super().__init__(queue=queue, polling_interval=interval, eager=False, run_forever=True)

    async def _prepare(self):
        pass

    async def _main(self, *args):

        def merge_reconnected_stations():
            try:
                idd_css = [cs for cs in mem_dao.retrieve_all() if cs.serial_number]
                idd_css.sort(key=lambda cs: cs.last_seen, reverse=True)
                if len(idd_css) < 1:
                    return
                oldest: ChargingStation = idd_css[0]
                if len(idd_css) > 1:
                    for cs in idd_css[1:]:
                        oldest.host = cs.host
                        oldest.port = cs.port
                        oldest.tags.update(cs.tags)
                        oldest.transactions.update(cs.transactions)
                        oldest.connectors.update(cs.connectors)
                        oldest.last_heartbeat = cs.last_heartbeat
                        mem_dao.delete(cs)
                mem_dao.update(oldest)
                oldest.reg_id = oldest.serial_number
                els_dao.update(oldest)
            except Exception as e:
                print(f'ElasticSync: Merging stations failed because: {e.with_traceback(e.__traceback__)}')

        def remove_unknown_stations():
            try:
                result = mem_dao.find_by({'serial_number': None})
                [mem_dao.delete(cs) for cs in result]
            except Exception as e:
                self._handle_exception(e)

        els_dao: ElasticSearchDAO = ElasticSearchDAOFactory('elocity', *self.service_urls).get_instance(ChargingStation)
        mem_dao: MemoryDAO = MemoryDAOFactory().get_instance(ChargingStation)
        merge_reconnected_stations()
        remove_unknown_stations()

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        pass
