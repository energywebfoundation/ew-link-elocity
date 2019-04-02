import asyncio
import datetime

import energyweb

from tasks.ocpp16.memorydao import DAOFactory
from tasks.ocpp16.ws_server import Ocpp16Server


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
