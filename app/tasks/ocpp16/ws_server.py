import asyncio
import json
import pprint

import websockets

from tasks.ocpp16.memorydao import MemoryDAOFactory, DAOFactory
from tasks.ocpp16.protocol import ChargingStation, Ocpp16


class Ocpp16Server:

    def __init__(self, factory: DAOFactory, queue: dict):
        self._queue = queue
        self._factory = factory

    def dispatcher(self, cs: ChargingStation, msg: Ocpp16.Request or Ocpp16.Response):
        """
        Manage state and dispatch incoming message to its designated Charging Station
        :param cs: ChargingStation
        :param msg: Message
        """
        # TODO: Search cs by serial_number and replace ID(host:port) with new address.
        cs_dao = self._factory.get_instance(ChargingStation)
        cs = cs_dao.persist(cs)
        if isinstance(msg, Ocpp16.Response):
            if msg.msg_id not in cs.req_queue:
                raise ConnectionError('Out-of-sync: Response for an unsent message.')
            msg.req = cs.req_queue[msg.msg_id]
        cs.follow_protocol(message=msg)
        cs_dao.update(cs)

    def aggregator(self) -> [Ocpp16.Request or Ocpp16.Response]:
        """
        Aggregate outgoing messages from all charging stations
        :return: [Messages]
        """
        messages = []
        cs_dao = self._factory.get_instance(ChargingStation)

        def gather(msg: Ocpp16.Request or Ocpp16.Response):
            if msg.is_pending:
                messages.append(msg)
                msg.is_pending = False

        for cs in cs_dao.retrieve_all():
            [gather(req) for req in cs.req_queue.values()]
            [gather(res) for res in cs.res_queue.values()]
            cs_dao.update(cs)
        return messages

    def get_server_future(self, host: str, port: int):

        clients_connected = set()

        async def outgoing(websocket, path):
            """ Send Messages from all charging stations queues """
            await asyncio.sleep(2)
            try:
                for msg in self.aggregator():
                    await websocket.send(json.dumps(msg.serialize()))
                    pp = pprint.PrettyPrinter(indent=4)
                    print(f">> {pp.pformat(msg.serialize())}\n")

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error in delegating outgoing messages: {e.with_traceback(e.__traceback__)}')

        async def wait_command():
            """ check_command_messages """
            try:
                cs_dao = self._factory.get_instance(ChargingStation)

                def execute(cs_id: str, method: str, kwargs: dict):
                    cs = cs_dao.retrieve(cs_id)
                    method = getattr(cs, method)
                    if callable(method):
                        method(**kwargs)
                    cs_dao.update(cs)

                cs_id, method, kwargs = await self._queue['ev_charger_command'].get()
                execute(cs_id, method, kwargs)
                while not self._queue['ev_charger_command'].empty():
                    cs_id, method, kwargs = self._queue['ev_charger_command'].get_nowait()
                    execute(cs_id, method, kwargs)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error processing command messages: {e.with_traceback(e.__traceback__)}')

        async def incoming(websocket, path):
            """ Listen to new messages and dispatch them """
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

                self.dispatcher(cs=cs, msg=msg)

                # notify_available_charging_stations
                cs_dao = self._factory.get_instance(ChargingStation)
                stations = {cs.reg_id for cs in cs_dao.retrieve_all()}
                await self._queue['ev_chargers_available'].put(stations)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error in processing incoming messages: {e.with_traceback(e.__traceback__)}')

        async def router(websocket, path):
            """ Route the messages to the different clients connected"""
            clients_connected.add(websocket)

            while True:
                try:
                    tasks = []
                    if not websocket.closed:
                        tasks.append(asyncio.ensure_future(incoming(websocket, path)))
                        tasks.append(asyncio.ensure_future(wait_command()))
                        tasks.append(asyncio.ensure_future(outgoing(websocket, path)))
                    else:
                        clients_connected.remove(websocket)
                        host, port = websocket.remote_address[0], websocket.remote_address[1]
                        print(f'Client {host}:{port} disconnected.')
                        break
                    if len(tasks) > 1:
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        [task.cancel() for task in pending]
                    else:
                        await asyncio.sleep(1)
                except Exception as e:
                    host, port = websocket.remote_address[0], websocket.remote_address[1]
                    print(f'Client {host}:{port} disconnected abruptly. {e.with_traceback(e.__traceback__)}')

        # Returns a future
        return websockets.serve(ws_handler=router, host=host, port=port, subprotocols=['ocpp1.6'])


async def command(queue: dict):
    """
    Examples of commands
    :return:
    """
    def get_cs_ids():
        return queue['ev_chargers_available'].get_nowait()

    async def unlock(cs_id: str):
        await queue['ev_charger_command'].put((cs_id, 'unlock_connector', {'connector_id': 1}))

    async def start(cs_id: str):
        await queue['ev_charger_command'].put((cs_id, 'start_transaction', {'tag_id': 1}))

    async def stop(cs_id: str):
        await queue['ev_charger_command'].put((cs_id, 'stop_transaction', {'tx_id': 1}))

    await asyncio.sleep(20)

    print('----- commands woke up -----')
    cs_ids = {}
    while not queue['ev_chargers_available'].empty():
        cs_ids = get_cs_ids()
    for cs_id in cs_ids:
        await unlock(cs_id)
        await asyncio.sleep(10)
        await start(cs_id)
        await asyncio.sleep(10)
        await stop(cs_id)
    print('---- end -----')


if __name__ == '__main__':
    try:

        IP = 'localhost'
        # IP = '192.168.123.220'
        PORT = 8080
        FACTORY = MemoryDAOFactory()
        QUEUE = {'ev_charger_command': asyncio.Queue(maxsize=10),
                 'ev_chargers_available': asyncio.Queue(maxsize=5)}
        server_cls = Ocpp16Server(FACTORY, QUEUE)
        future = server_cls.get_server_future(IP, PORT)
        print(f'Server started at http://{IP}:{PORT}.')
        asyncio.get_event_loop().run_until_complete(future)
        asyncio.get_event_loop().run_until_complete(command(QUEUE))
        asyncio.get_event_loop().run_forever()
    except Exception as e:
        print(f'Server failed because {e.with_traceback(e.__traceback__)}')
        try:
            future.ws_server.close()
            print('Server stopped')
        except:
            print(f'Port {PORT} is busy or host {IP} is not assigned.')
