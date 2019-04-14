import datetime
import uuid

import elasticsearch
import energyweb

from tasks.database.elasticdao import ElasticSearchDAO
from tasks.database.memorydao import MemoryDAO, MemoryDAOFactory
from tasks.ocpp16.protocol import ChargingStation


class ElasticSyncTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, interval: datetime.timedelta, service_urls: tuple):
        self.service_urls = service_urls
        energyweb.Task.__init__(self, queue=queue, polling_interval=interval, eager=False, run_forever=True)
        energyweb.Logger.__init__(self, 'ElasticSync')

    async def _prepare(self):
        pass

    async def _main(self, *args):

        def merge_reconnected_stations():
            merged_css = []
            cs_index = {csk.serial_number: [cs for cs in mem_dao.retrieve_all() if csk.serial_number]
                        for csk in mem_dao.retrieve_all() if csk.serial_number}
            for css in cs_index.values():
                css.sort(key=lambda cs: cs.last_seen, reverse=True)
                if len(css) > 0:
                    oldest: ChargingStation = css.pop()
                    for cs in css:
                        oldest.host = cs.host
                        oldest.port = cs.port
                        oldest.tags.update(cs.tags)
                        oldest.transactions.update(cs.transactions)
                        oldest.connectors.update(cs.connectors)
                        oldest.last_heartbeat = cs.last_heartbeat
                        mem_dao.delete(cs)
                    mem_dao.update(oldest)
                    merged_css.append(oldest)
            return merged_css

        def remove_unknown_stations():
            try:
                result = mem_dao.find_by({'serial_number': None})
                [mem_dao.delete(cs) for cs in result]
            except Exception as e:
                pass

        def update_elastic():
            for cs in merged:
                cs.reg_id = cs.serial_number
                for tag in cs.tags.values():
                    tag.reg_id = tag.tag_id
                    tag.last_used_in = cs.reg_id
                    els_tg_dao.update(tag)
                cs.tags = {}
                for tx in cs.transactions.values():
                    if tx.meter_start and tx.meter_stop:
                        tx.reg_id = uuid.uuid4()
                        tx.cs_reg_id = cs.reg_id
                        els_tx_dao.update(tx)
                cs.transactions = {}
                els_cs_dao.update(cs)

        els_cs_dao = ElasticSearchDAO('charging-stations', ChargingStation, *self.service_urls)
        els_tx_dao = ElasticSearchDAO('transactions', ChargingStation.Transaction, *self.service_urls)
        els_tg_dao = ElasticSearchDAO('tags', ChargingStation.Tag, *self.service_urls)
        mem_dao: MemoryDAO = MemoryDAOFactory().get_instance(ChargingStation)
        try:
            merged = merge_reconnected_stations()
            remove_unknown_stations()
            update_elastic()
            self.console.debug('Synced memory with elastic search.')
        except elasticsearch.ElasticsearchException as e1:
            pass
        except Exception as e2:
            self._handle_exception(e2)

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        self.console.error(f'ElasticSync: Merging stations failed because: {e.with_traceback(e.__traceback__)}')
