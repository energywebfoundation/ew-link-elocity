import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as response

host = "0.0.0.0"
port = 9069
path = '/etc/elocity'


app = Sanic('ConfigApi')


@app.post("/config")
async def post_config(request: Request):
    try:
        global path
        file_name = 'ew-link.config'
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, file_name)
        with open(path, 'w+') as file:
            json.dump(request.json, file)
        return response({'message': 'file successfully saved. restart device to apply changes.',
                         'path': f'{path}'})
    except Exception as e:
        return response({'message': f'file not saved because {e.with_traceback(e.__traceback__)}'},
                        status=500)


def _handle_exception(e: Exception):
    print(f'ConfigApi failed because {e.with_traceback(e.__traceback__)}')


if __name__ == "__main__":
    app.run(host=host, port=port, access_log=True)