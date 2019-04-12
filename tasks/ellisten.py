import datetime

import elasticsearch
import energyweb

from tasks.database.dao import Model
from tasks.database.elasticdao import ElasticSearchDAO
from tasks.database.memorydao import MemoryDAOFactory, MemoryDAO
from tasks.ocpp16.protocol import ChargingStation


class DbListenTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, interval: datetime.timedelta, service_urls: tuple):
        self.service_urls = service_urls
        self.available_stations = {}
        energyweb.Task.__init__(self, queue=queue, polling_interval=interval, eager=False, run_forever=True)
        energyweb.Logger.__init__(self, 'DbListenTask')

    class Command(Model):

        def __init__(self, command, cs_id, tag_id, received=False):
            self.command = command
            self.tag_id = tag_id
            self.cs_id = cs_id
            self.received: bool = received
            super().__init__()

        @staticmethod
        def from_dict(obj_dict: dict):
            return DbListenTask.Command(**obj_dict)

    async def _prepare(self):
        pass

    async def _main(self, *args):

        def create_message() -> tuple:
            cs_add = self.available_stations[cmd.cs_id]
            if cmd.command == 'start_transaction':
                payload = {'tag_id': cmd.tag_id}
            elif cmd.command == 'stop_transaction':
                cs: ChargingStation = mem_dao.retrieve(cs_add)
                txs = [tx for k, tx in cs.transactions.items() if not tx.meter_stop]
                if len(txs) > 0:
                    txs.sort(key=lambda tx: tx.time_start)
                    tx: ChargingStation.Transaction = txs.pop()
                    payload = {'tx_id': tx.tx_id}
                else:
                    return None

            elif cmd.command == 'unlock_connector':
                payload = {'connector_id': 1}
            else:
                return None
            return cs_add, cmd.command, payload

        while not self.queue['ev_chargers_available'].empty():
            self.available_stations.update(self.queue['ev_chargers_available'].get_nowait())

        cmd_dao = ElasticSearchDAO('charging-control', DbListenTask.Command, *self.service_urls)
        mem_dao: MemoryDAO = MemoryDAOFactory().get_instance(ChargingStation)

        try:
            for cmd in cmd_dao.query({"bool": {"must": [{"exists": {"field": 'command'}},
                                                        {"match": {"received": False}}]}}):
                if cmd.cs_id not in self.available_stations:
                    return
                message = create_message()
                if message:
                    self.console.debug(f'DbListen sent msg: {message}')
                    await self.queue['ev_charger_command'].put(message)
                    cmd.received = True
                    cmd_dao.delete(cmd)

        except elasticsearch.ElasticsearchException as e1:
            self._handle_exception(e1)
        except Exception as e2:
            self._handle_exception(e2)

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        self.console.error(f'DbListen failed because {e.with_traceback(e.__traceback__)}')
