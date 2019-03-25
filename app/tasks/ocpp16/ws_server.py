import asyncio
import json
import pprint

import websockets

from tasks.ocpp16.memorydao import MemoryDAOFactory
from tasks.ocpp16.protocol import ChargingStation, Ocpp16

# IP = 'localhost'
IP = '192.168.123.220'
PORT = 8080
FACTORY = MemoryDAOFactory()

stateful_cs = FACTORY.get_instance(ChargingStation)

message_bus = {}
message_bus['ev_charger_command'] = asyncio.Queue(maxsize=10)
message_bus['ev_charger_available'] = asyncio.Queue(maxsize=5)


async def incoming(websocket, path):

    async def dispatcher(cs: ChargingStation, incoming: Ocpp16.Request or Ocpp16.Response):
        """
        Manage state and dispatch incoming message to its designated Charging Station
        :param cs: ChargingStation
        :param incoming: Message
        """
        cs = stateful_cs.persist(cs)
        if isinstance(incoming, Ocpp16.Response):
            if incoming.msg_id not in cs.req_queue:
                raise ConnectionError('Out-of-sync: Response for an unsent message.')
            incoming.req = cs.req_queue[incoming.msg_id]
        cs.handle_protocol(message=incoming)
        stateful_cs.update(cs)
        # notify_available_charging_stations
        global message_bus
        stations = {cs.reg_id for cs in stateful_cs.retrieve_all()}
        await message_bus['ev_charger_available'].put(stations)

    try:
        packet = json.loads(await websocket.recv())
        if len(packet) < 1 or packet[0] not in (2, 3):
            print(f'<< UNKNOWN PACKET {packet}')
            return None

        msg = Ocpp16.Request(*packet) if packet[0] == 2 else Ocpp16.Response(*packet)
        host, port = websocket.remote_address[0], websocket.remote_address[1]
        cs = ChargingStation(host, port)

        pp = pprint.PrettyPrinter(indent=4)
        print(f"<< {cs.reg_id}:  {pp.pformat(msg.serialize())}\n")

        await dispatcher(cs=cs, incoming=msg)
    except Exception as e:
        pass
    if not websocket.closed:
        await asyncio.ensure_future(incoming(websocket, path))


async def outcoming(websocket, path):

    def aggregator() -> [Ocpp16.Request or Ocpp16.Response]:
        """
        Aggregate outgoing messages from all charging stations
        :return: [Messages]
        """
        queue = []

        def add_to_queue(msg: Ocpp16.Request or Ocpp16.Response, cs: ChargingStation):
            queue.append(msg)
            msg.is_pending = False
            stateful_cs.update(cs)

        # check_command_messages
        global message_bus
        while not message_bus['ev_charger_command'].empty():
            cs_id, method, kwargs = message_bus['ev_charger_command'].get_nowait()
            cs = stateful_cs.retrieve(cs_id)
            method = getattr(cs, method)
            if callable(method):
                method(**kwargs)
            stateful_cs.update(cs)

        for cs in stateful_cs.retrieve_all():
            [add_to_queue(req, cs) for req in cs.req_queue.values() if req.is_pending]
            [add_to_queue(res, cs) for res in cs.res_queue.values() if res.is_pending]
        return queue
    #   - Send Messages from all charging stations queues
    try:
        for msg in aggregator():
            await websocket.send(json.dumps(msg.serialize()))
            pp = pprint.PrettyPrinter(indent=4)
            print(f">> {pp.pformat(msg.serialize())}\n")
    except Exception as e:
        pass
    if not websocket.closed:
        await asyncio.ensure_future(outcoming(websocket, path))

connected = set()


async def router(websocket, path):
    connected.add(websocket)
    # TODO: Fix multiple connections by creating a function here to add new listeners.
    while True:
        try:
            tasks = []
            for ws in connected:
                if not ws.closed:
                    tasks.append(asyncio.ensure_future(incoming(ws, path)))
                    tasks.append(asyncio.ensure_future(outcoming(ws, path)))
                else:
                    connected.remove(ws)
                    host, port = ws.remote_address[0], ws.remote_address[1]
                    print(f'Client {host}:{port} disconnected.')
                    break
            if len(tasks) > 1:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                [task.cancel() for task in pending]
            else:
                await asyncio.sleep(1)
        except Exception as e:
            print('Client disconnected abruptly.')


async def command():
    # import code
    # global message_bus
    #
    # def get_cs_ids():
    #     return message_bus['ev_charger_available'].get_nowait()
    #
    # async def unlock(cs_id: str):
    #     await message_bus['ev_charger_command'].put((cs_id, 'unlock_connector', {'connector_id': 1}))
    #
    # async def start(cs_id: str):
    #     await message_bus['ev_charger_command'].put((cs_id, 'start_transaction', {'tag_id': 1}))
    #
    # async def stop(cs_id: str):
    #     await message_bus['ev_charger_command'].put((cs_id, 'stop_transaction', {'tx_id': 1}))
    #
    # code.interact(local=dict(globals(), **locals()))

    await asyncio.sleep(120)
    print('----- commands woke up -----')
    cs_ids = {}
    global message_bus
    while not message_bus['ev_charger_available'].empty():
        cs_ids = message_bus['ev_charger_available'].get_nowait()
    for cs_id in cs_ids:
        await message_bus['ev_charger_command'].put((cs_id, 'unlock_connector', {'connector_id': 1}))
        await asyncio.sleep(60)
        await message_bus['ev_charger_command'].put((cs_id, 'start_transaction', {'tag_id': 1}))
        await asyncio.sleep(120)
        await message_bus['ev_charger_command'].put((cs_id, 'stop_transaction', {'tx_id': 1}))
    print('---- end -----')


server = websockets.serve(ws_handler=router, host=IP, port=PORT, subprotocols=['ocpp1.6'])


if __name__ == '__main__':
    try:
        print(f'Server started at http://{IP}:{PORT}.')
        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_until_complete(command())
        asyncio.get_event_loop().run_forever()
    except Exception as e:
        # TODO: log server error.
        try:
            server.ws_server.close()
            print('Server stopped')
        except:
            print(f'Port {PORT} is busy or host {IP} is not assigned.')
