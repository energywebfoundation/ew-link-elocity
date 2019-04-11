import datetime
from copy import deepcopy

import energyweb


class IotLayerEventsTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, interval: datetime.timedelta, client_url: str, contract_add: str, device_id: str,
                 wallet_add: str = None, wallet_pwd: str = None, max_retries: int = 2, retry_pause: int = 3,
                 block_sync: int = 1):
        """ Wallet data is not needed once no tx is sent to the blockchain """
        self.device_id = device_id
        self.block_sync = block_sync
        self.contract_name = 'rental'
        contract_abi = deepcopy(energyweb.iotlayer)
        contract_abi['address'] = contract_add
        smart_contract = {
            "client_url": client_url,
            "contracts": {self.contract_name: contract_abi},
            "credentials": (wallet_add, wallet_pwd),
            "max_retries": max_retries,
            "retry_pause": retry_pause
        }
        self.client = energyweb.EVMSmartContractClient(**smart_contract)
        self.rented_filter = None
        self.returned_filter = None
        self.available_stations = {}
        energyweb.Task.__init__(self, queue=queue, polling_interval=interval, eager=False, run_forever=True)
        energyweb.Logger.__init__(self, 'IotLayerEvents')

    async def _prepare(self):
        if not self.rented_filter or not self.returned_filter:
            filter_params = {
                "contract_name": self.contract_name,
                "event_name": 'LogRented',
                "block_count": 1
            }
            self.rented_filter = self.client.create_event_filter(**filter_params)
            filter_params['event_name'] = 'LogReturned'
            self.returned_filter = self.client.create_event_filter(**filter_params)

    async def _main(self, *args):

        def check_start_events():
            for event in self.rented_filter.get_new_entries():
                # session_id = Web3.toHex(event['transactionHash'])
                if self.device_id in self.available_stations:
                    cs_id = self.available_stations[self.device_id]
                    await self.queue['ev_charger_command'].put((cs_id, 'start_transaction', {'tag_id': 1}))
                else:
                    self.console.error(f'IotLayerEventsTask failed to START charging because {cs_sn} is not available.')

        def check_stop_events():
            for event in self.returned_filter.get_new_entries():
                if self.device_id in self.available_stations:
                    cs_id = self.available_stations[self.device_id]
                    await self.queue['ev_charger_command'].put((cs_id, 'stop_transaction', {'tx_id': 1}))
                else:
                    self.console.error(f'IotLayerEventsTask failed to STOP charging because {cs_sn} is not available.')

        while not self.queue['ev_chargers_available'].empty():
            self.available_stations.update(self.queue['ev_chargers_available'].get_nowait())

        try:
            check_start_events()
        except Exception as e:
            self._handle_exception(e)

        try:
            check_stop_events()
        except Exception as e:
            self._handle_exception(e)

    async def _finish(self):
        self.console.error('IotLayerEventsTask filters failed. Rebooting.')

    def _handle_exception(self, e: Exception):
        pass
