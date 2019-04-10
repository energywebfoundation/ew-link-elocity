import datetime

import energyweb


class IotLayerEventsTask(energyweb.Task, energyweb.Logger):

    def __init__(self, queue: dict, interval: datetime.timedelta, client_url: str, wallet_add: str, wallet_pwd: str):
        self.client_url = client_url
        self.wallet_add = wallet_add
        self.wallet_pwd = wallet_pwd
        self.contract = {'usn': energyweb.usn.contract}
        energyweb.Task.__init__(self, queue=queue, polling_interval=interval, eager=False, run_forever=True)
        energyweb.Logger.__init__(self, 'IotLayerEvents')

    async def _prepare(self):
        pass

    async def _main(self, *args):
        try:
            smart_contract = {
                "client_url": self.client_url,
                "contracts": self.contract,
                "credentials": (self.wallet_add, self.wallet_pwd),
                "max_retries": 100,
                "retry_pause": 3
            }
            usn_contract = energyweb.EVMSmartContractClient(**smart_contract)
            usn_filter = usn_contract.getEventFilter(contract_name='usn', event_name='LogRented')
            event_logs = usn_filter.get_all_entries()
            sessionId = Web3.toHex(event_logs[-1]['transactionHash'])
        except:
            sessionId = '0x4d178529541264bd29baac17665f518cb9f1c819342a161f1f73701f18a40a60'

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        pass




