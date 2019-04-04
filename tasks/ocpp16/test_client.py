"""
Test client for server.py with real collected data.
"""

import asyncio
import json

import websockets

IP = '0.0.0.0'
# IP = '192.168.123.220'
PORT = 80

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

status_notification2 = [2, '97764672', 'StatusNotification',
                        {
                            'connectorId': 0,
                            'errorCode': 'NoError',
                            'info': 'Status Update',
                            'status': 'Available',
                            'timestamp': '2019-03-22T11:06:22Z',
                            'vendorId': 'Bender GmbH Co. KG'
                        }]

authorize_request = [2, '73102556', 'Authorize', {'idTag': '1'}]

start_transaction = [2, '121599829', 'StartTransaction',
                     {
                         'connectorId': 1,
                         'idTag': '1',
                         'meterStart': 1528,
                         'timestamp': '2019-03-25T14:34:14Z'
                     }]

stop_transaction = [2, '107993865', 'StopTransaction',
                    {
                        'idTag': '1',
                        'meterStop': 1704,
                        'reason': 'Local',
                        'timestamp': '2019-03-25T14:53:59Z',
                        'transactionData': [
                            {'sampledValue':
                                [
                                    {'context': 'Transaction.Begin',
                                     'format': 'Raw',
                                     'location': 'Outlet',
                                     'measurand': 'Energy.Active.Import.Register',
                                     'unit': 'Wh',
                                     'value': '1528'
                                     }], 'timestamp': '2019-03-25T14:34:14Z'
                            },
                            {'sampledValue': [
                                {'context': 'Transaction.End',
                                 'format': 'Raw',
                                 'location': 'Outlet',
                                 'measurand': 'Energy.Active.Import.Register',
                                 'unit': 'Wh',
                                 'value': '1704'
                                 }], 'timestamp': '2019-03-25T14:53:59Z'
                            }], 'transactionId': 255
                    }]


async def hello():
    async with websockets.connect(f'ws://{IP}:{PORT}') as websocket:
        # Boot
        await websocket.send(json.dumps(boot_notification))
        print(f"> {boot_notification}")
        boot_ack = await websocket.recv()
        print(f"<< {boot_ack}")
        # Status change
        await websocket.send(json.dumps(status_notification))
        print(f"> {status_notification}")
        await websocket.send(json.dumps(status_notification2))
        print(f"> {status_notification2}")
        status_ack = await websocket.recv()
        print(f"<< {status_ack}")
        status_ack = await websocket.recv()
        print(f"<< {status_ack}")
        # autorize
        await websocket.send(json.dumps(authorize_request))
        print(f"> {authorize_request}")
        status_ack = await websocket.recv()
        print(f"<< {status_ack}")
        # start transaction
        await websocket.send(json.dumps(start_transaction))
        print(f"> {start_transaction}")
        status_ack = await websocket.recv()
        print(f"<< {status_ack}")
        # stop transaction
        await websocket.send(json.dumps(stop_transaction))
        print(f"> {stop_transaction}")
        status_ack = await websocket.recv()
        print(f"<< {status_ack}")

        msg = json.loads(await websocket.recv())
        print(f"<< {msg}")

        websocket.close()


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(hello())
