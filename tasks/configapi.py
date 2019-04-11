import datetime
import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as response

import energyweb


class ConfigApi(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, interval: datetime.timedelta):
        self.server = None
        self.host = "127.0.0.1"
        self.port = 8000
        self.path = '/opt/slockit/configs'
        energyweb.Task.__init__(self, queue=queue, polling_interval=interval, eager=False, run_forever=True)
        energyweb.Logger.__init__(self, self.__class__.__name__)

    async def _prepare(self):
        self.console.debug('Config api running')

    async def _main(self, *args):

        app = Sanic('ConfigApi', configure_logging=False)

        @app.post("/config")
        async def post_config(request: Request):
            self.path = '/opt/slockit/configs'
            file_name = 'ew-link.config'
            if not os.path.exists(self.path):
                os.makedirs(self.path)
            path = os.path.join(self.path, file_name)
            with open(path, 'w+') as file:
                json.dump(request.json, file)
            return response({'message': 'file successfully saved. restart device to apply changes.', 'path': f'{path}'})

        try:
            self.server = app.create_server(host=self.host, port=self.port, return_asyncio_server=True)
            await self.server
        except KeyboardInterrupt:
            if self.server:
                self.server.close()
        except Exception as e:
            self._handle_exception(e)

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        self.console.exception(f'ConfigApi failed because {e.with_traceback(e.__traceback__)}')
