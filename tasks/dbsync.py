import datetime
import uuid

import energyweb

from tasks.database.elasticdao import ElasticSearchDAO, ElasticSearchDAOFactory
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
                self._handle_exception(e)

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

        els_cs_dao: ElasticSearchDAO = ElasticSearchDAOFactory('charging-stations', *self.service_urls).\
            get_instance(ChargingStation)
        els_tx_dao: ElasticSearchDAO = ElasticSearchDAOFactory('transactions', *self.service_urls).\
            get_instance(ChargingStation.Transaction)
        els_tg_dao: ElasticSearchDAO = ElasticSearchDAOFactory('tags', *self.service_urls).\
            get_instance(ChargingStation.Tag)
        mem_dao: MemoryDAO = MemoryDAOFactory().get_instance(ChargingStation)
        try:
            merged = merge_reconnected_stations()
            remove_unknown_stations()
            update_elastic()
            self.console.debug('Synced memory with elastic search.')
        except Exception as e:
            self.console.error(f'ElasticSync: Merging stations failed because: {e.with_traceback(e.__traceback__)}')

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        pass
