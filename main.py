import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as response

host = "0.0.0.0"
port = 9069
path = os.path.join('/etc', 'elocity', 'ew-link.config')


app = Sanic('ConfigApi')

cors_headers = {"Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Origin,X-Requested-With,Content-Type,Accept",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE"}


def _fail_response(e):
    return response({'message': f'file not saved because {e.with_traceback(e.__traceback__)}'}, status=500,
                    headers=cors_headers)


@app.post("/config")
async def post_config(request: Request):
    try:
        global path
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, 'w+') as file:
            json.dump(request.json, file)
        return response({'message': 'file successfully saved. restart device to apply changes.',
                         'path': f'{path}'}, headers=cors_headers)
    except Exception as e:
        return _fail_response(e)


@app.delete("/config")
async def del_config(request: Request):
    try:
        if not os.path.exists(path):
            return _fail_response(FileNotFoundError('App not configured.'))
        os.remove(path)
        return response({'message': 'configuration deleted, post new.', 'path': f'{path}'}, headers=cors_headers)
    except Exception as e:
        return _fail_response(e)


@app.options("/config")
async def ops_config(request: Request):
    return response({}, headers=cors_headers)


if __name__ == "__main__":
    app.run(host=host, port=port, access_log=True)