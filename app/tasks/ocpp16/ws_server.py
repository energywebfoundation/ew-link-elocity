import asyncio
import json
import pprint

import websockets

from app.tasks.ocpp16.memorydao import MemoryDAOFactory
from app.tasks.ocpp16.protocol import ChargingStation, Ocpp16

IP = '192.168.123.220'
PORT = 8080
FACTORY = MemoryDAOFactory()

stateful_cs = FACTORY.get_instance(ChargingStation)


async def router(websocket, path):
    """
    Route OCPP incoming and outgoing messages
    :param websocket: yielded from websockets library
    :param path: ?
    """
    # TODO: check about awaiting or not

    def aggregator() -> [Ocpp16.Request or Ocpp16.Response]:
        """
        Aggregate outgoing messages from all charging stations
        :return: [Messages]
        """
        requests, responses = [], []
        requests = [requests + cs.req_queue for cs in stateful_cs.retrieve_all()]
        responses = [responses + cs.res_queue for cs in stateful_cs.retrieve_all()]
        queue = responses + requests
        return [msg for msg in queue if msg.is_pending]

    def dispatcher(cs: ChargingStation, incoming: Ocpp16.Request or Ocpp16.Response):
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

    def console_log(msg: Ocpp16.Request or Ocpp16.Response, direction: str):
        pp = pprint.PrettyPrinter(indent=4)
        print(f"{direction} {pp.pformat(msg.serialize())}\n")

    #   - Send Messages from all charging stations queues
    for outcoming in aggregator():
        await websocket.send(json.dumps(outcoming.serialize()))
        outcoming.is_pending = False
        console_log(outcoming, '>>')

    #   - Receive a new message and route it
    packet = json.loads(await websocket.recv())
    if len(packet) < 1 or packet[0] not in (2, 3):
        print(f'<< UNKNOWN PACKET {packet}')
        return None
    incoming = Ocpp16.Request(*packet) if packet[0] == 2 else Ocpp16.Response(*packet)
    console_log(incoming, '<<')
    cs = ChargingStation(*websocket.remote_address())  # remote_address returns host, port
    dispatcher(cs=cs, incoming=incoming)


server = websockets.serve(ws_handler=router, host=IP, port=PORT, subprotocols=['ocpp1.6'])

if __name__ == '__main__':
    try:
        print('Server started')
        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_forever()
    except:
        server.ws_server.close()
        print('Server stopped')
