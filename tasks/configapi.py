import asyncio
import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as response


app = Sanic(__name__)


@app.post("/config")
async def post_config(request: Request):
    path = '/opt/slockit/configs'
    file_name = 'ew-link.config'
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(path, file_name)
    with open(path, 'w+') as file:
        json.dump(request.json, file)
    return response({'message': 'file successfully saved', 'path': f'{path}'})

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        srv_coro = app.create_server(host="127.0.0.1", port=8000, return_asyncio_server=True)
        loop.run_until_complete(srv_coro)
        loop.run_forever()
        # assert srv.is_serving() is False
        # loop.run_until_complete(srv.start_serving())
        # assert srv.is_serving() is True
        # loop.run_until_complete(srv.serve_forever())
    except KeyboardInterrupt:
        loop.close()