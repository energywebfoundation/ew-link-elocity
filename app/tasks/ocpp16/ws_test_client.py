import asyncio
import json

import websockets
from app.tasks.ocpp16.ws_server import IP, PORT

boot_notification = [2, '52325482', 'BootNotification',
                     {
                         'chargeBoxSerialNumber': '1702502754/B94060001',
                         'chargePointModel': 'CC612_1M3PR',
                         'chargePointSerialNumber': 'Not Set',
                         'chargePointVendor': 'Bender GmbH Co. KG',
                         'firmwareVersion': '4.32-4932',
                         'iccid': '42:EB:EE:61:1A:CA',
                         'imsi': 'usb0',
                         'meterSerialNumber': '0901454d4800007340d2',
                         'meterType': 'eHz/EDL40'
                     }]

status_notification = [2, '97764671', 'StatusNotification',
                       {
                           'connectorId': 0,
                           'errorCode': 'NoError',
                           'info': 'Status Update',
                           'status': 'Available',
                           'timestamp': '2019-03-22T11:06:22Z',
                           'vendorId': 'Bender GmbH Co. KG'
                       }]


async def hello():
    async with websockets.connect(f'ws://{IP}:{PORT}') as websocket:

        await websocket.send(json.dumps(boot_notification))
        print(f"> {boot_notification}")
        boot_ack = await websocket.recv()
        print(f"< {boot_ack}")

        await websocket.send(json.dumps(status_notification))
        print(f"> {status_notification}")
        status_ack = await websocket.recv()
        print(f"< {status_ack}")

        msg = json.loads(await websocket.recv())
        print(f"< {msg}")

        websocket.close()


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(hello())
