import asyncio
import datetime

import energyweb

from tasks.database.dao import DAOFactory, DAO
from tasks.database.elasticdao import ElasticSearchDAOFactory
from tasks.ocpp16.protocol import ChargingStation
from tasks.ocpp16.server import Ocpp16Server


class CustomOcpp16Server(Ocpp16Server):

    def __init__(self, factory, queue, console):
        self.console = console
        super().__init__(factory, queue)

    def _message_handler(self, msg):
        self.console.debug(f'{msg.serialize()}')

    def _error_handler(self, text, e):
        self.console.error(f'{text}{e.with_traceback(e.__traceback__)}')


class Ocpp16ServerTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, factory: DAOFactory, host: str, port: int):
        """ Use different DAOs to change storage services """
        self._queue = queue
        self._factory = factory
        self.server_address = (host, port)
        self._future = None
        energyweb.Task.__init__(self, queue, polling_interval=datetime.timedelta(minutes=5), eager=True, run_forever=True)
        energyweb.Logger.__init__(self, 'Ocpp16Server')

    async def _prepare(self):
        if not {'ev_charger_command', 'ev_chargers_available'}.issubset(self._queue.keys()):
            raise AssertionError("Please register queues 'ev_charger_command' and 'ev_chargers_available' on the app.")
        server = CustomOcpp16Server(self._factory, self._queue, self.console)
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


class ElasticCleanUp(energyweb.Task):

    def __init__(self, queue: dict, service_urls: tuple):
        self.service_urls = service_urls
        super().__init__(queue=queue, polling_interval=datetime.timedelta(minutes=3), eager=False, run_forever=True)

    async def _prepare(self):
        pass

    async def _main(self, *args):

        def merge_reconnected_stations(cs_dao: DAO):
            try:
                query = {"query": {"bool": {"must": {"script": {"script":
                        {"source": "doc['serial_number'].value ==  doc['serial_number'].value",
                         "lang": "painless"}}}}},
                         "sort": [{"arbitraryDate": {"order": "desc"}}]}
                results = cs_dao.query(query)
                oldest: ChargingStation = results[0]
                for cs in results[1:].reverse():
                    oldest.host = cs.host
                    oldest.port = cs.port
                    oldest.tags.update(cs.tags)
                    oldest.transactions.update(cs.transactions)
                    oldest.connectors.update(cs.connectors)
                    oldest.last_heartbeat = cs.last_heartbeat
                    cs_dao.delete(cs)
            except Exception as e:
                self._handle_exception(e)

        def remove_unknown_stations(cs_dao: DAO):
            try:
                cs_dao.delete_all_blank('serial_number')
            except Exception as e:
                self._handle_exception(e)

        factory = ElasticSearchDAOFactory('elocity', *self.service_urls)
        cs_dao = factory.get_instance(ChargingStation)
        merge_reconnected_stations(cs_dao)
        remove_unknown_stations(cs_dao)

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        pass
