import datetime

import energyweb

from tasks.ocpp16.memorydao import DAOFactory
from tasks.ocpp16.ws_server import Ocpp16Server


class Ocpp16ServerTask(energyweb.Task):

    def __init__(self, queue: dict, factory: DAOFactory, host: str, port: int):
        self._queue = queue
        self._factory = factory
        self._server = Ocpp16Server(factory=factory, queue=queue)
        self.server_address = (host, port)
        self._future = None
        energyweb.Task.__init__(self, queue, polling_interval=datetime.timedelta(minutes=5), eager=True, run_forever=True)

    async def _prepare(self):
        if not {'ev_charger_command', 'ev_chargers_available'}.issubset(self._queue.keys()):
            raise AssertionError("Please register queues 'ev_charger_command' and 'ev_chargers_available' on the app.")
        self._future = self._server.get_server_future(*self.server_address)

    def _handle_exception(self, e: Exception):
        print(f'Ocpp16 Server failed because {e.with_traceback(e.__traceback__)}')

    async def _main(self):
        await self._future

    async def _finish(self):
        try:
            self._future.ws_server.close()
        except Exception as e:
            self._handle_exception(e)
