import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as response

host = "0.0.0.0"
port = 9069
path = os.path.join('/etc', 'elocity', 'ew-link.config')


app = Sanic('ConfigApi')


def _fail_response(e):
    return response({'message': f'file not saved because {e.with_traceback(e.__traceback__)}'}, status=500)


@app.post("/config")
async def post_config(request: Request):
    try:
        global path
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, 'w+') as file:
            json.dump(request.json, file)
        return response({'message': 'file successfully saved. restart device to apply changes.',
                         'path': f'{path}'})
    except Exception as e:
        return response({'message': f'file not saved because {e.with_traceback(e.__traceback__)}'},
                        status=500)


@app.delete("/config")
async def del_config(request: Request):
    try:
        if not os.path.exists(path):
            return _fail_response(FileNotFoundError('App not configured.'))
        os.remove(path)
        return response({'message': 'configuration deleted, post new.', 'path': f'{path}'})
    except Exception as e:
        return _fail_response(e)


if __name__ == "__main__":
    app.run(host=host, port=port, access_log=True)