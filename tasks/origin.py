import asyncio
import datetime

import energyweb

from energyweb.config import CooV1ConsumerConfiguration, CooV1ProducerConfiguration


class CooGeneralTask(energyweb.Logger, energyweb.Task):

    def __init__(self, task_config: energyweb.config.CooV1ConsumerConfiguration, polling_interval: datetime.timedelta,
                 queue: asyncio.Queue, store: str = '', enable_debug: bool = False):
        """
        :param task_config: Consumer configuration class instance
        :param polling_interval: Time interval between interrupts check
        :param store: Path to folder where the log files will be stored in disk. DEFAULT won't store data in-disk.
        :param enable_debug: Enabling debug creates a log for errors. Needs storage. Please manually delete it.
        """
        self.task_config = task_config
        self.chain_file_name = 'origin.pkl'
        self.msg_success = 'minted %s watts - block # %s'
        self.msg_error = 'energy_meter: %s - stack: %s'
        energyweb.Logger.__init__(self, log_name=task_config.name, store=store, enable_debug=enable_debug)
        energyweb.Task.__init__(self, queue=queue, polling_interval=polling_interval, eager=False, run_forever=True)

    def _log_measured_energy(self):
        """
        Try to reach the energy_meter and logs the measured energy.
        Wraps the complexity of the data read and the one to be written to the smart-contract
        """
        try:
            # Get the data by accessing the external energy device
            # Storing logs locally
            if self.store:
                local_storage = energyweb.DiskStorage(path_to_files=self.store,
                                                      chain_file_name=self.chain_file_name)
                last_file_hash = local_storage.get_last_hash()
                energy_data = self._transform(local_file_hash=last_file_hash)
                if not energy_data.is_meter_down:
                    local_chain_file = local_storage.add_to_chain(data=energy_data)
                    self.console.debug('%s created', local_chain_file)
            else:
                last_chain_hash = self.task_config.smart_contract.last_hash()
                energy_data = self._transform(local_file_hash=last_chain_hash)
            # Logging to the blockchain
            tx_receipt = self.task_config.smart_contract.mint(energy_data)
            block_number = str(tx_receipt['blockNumber'])
            self.console.debug(self.msg_success, energy_data.to_dict(), block_number)
        except ConnectionError as e:
            self.console.warning('Not minted, Smart-contract is unreachable.')
        except Exception as e:
            self._handle_exception(e)

    def _transform(self, local_file_hash: str):
        """
        Transforms the raw external energy data into blockchain format. Needs to be implemented for each different
        smart-contract and configuration type.
        """
        raise NotImplementedError

    def _fetch_remote_data(self, ip: energyweb.IntegrationPoint) -> (energyweb.ExternalData, bool):
        """
        Tries to reach external device for data.
        Returns smart-contract friendly data and logs error in case of failing.
        :param ip: Energy or Carbon Emission Device
        :return: Energy or Carbon Emission Data, Is device offline flag
        """
        try:
            result = ip.read_state()
            if not issubclass(result.__class__, energyweb.ExternalData):
                raise AssertionError('Make sure to inherit ExternalData when reading data from IntegrationPoint.')
            return result, False
        except Exception as e:
            self._handle_exception(e)
            return None, True

    async def _prepare(self):
        """
        Outputs the logger configuration
        """
        message = '[CONFIG] name: %s - energy energy_meter: %s'
        if self.store and self.enable_debug:
            self.console.info('[CONFIG] path to logs: %s', self.store)
        self.console.info(message, self.task_config.name, self.task_config.energy_meter.__class__.__name__)

    async def _main(self, duration: int = 3):
        self._log_measured_energy()

    async def _finish(self):
        pass

    def _handle_exception(self, e: Exception):
        # TODO debug log self.error_log
        self.console.exception(self.msg_error, self.task_config.energy_meter.__class__.__name__, e)


class CooProducerTask(CooGeneralTask):

    def __init__(self, task_config: CooV1ProducerConfiguration, polling_interval: datetime.timedelta,
                 queue: asyncio.Queue, store: str = None, enable_debug: bool = False):
        """
        :param task_config: Producer configuration class instance
        :param polling_interval: Time interval between interrupts check
        :param queue: For thread safe messaging between tasks
        :param store: Path to folder where the log files will be stored in disk. DEFAULT won't store data in-disk.
        :param enable_debug: Enabling debug creates a log for errors. Needs storage. Please manually delete it.
        """
        super().__init__(task_config=task_config, polling_interval=polling_interval, store=store, queue=queue,
                         enable_debug=enable_debug)

    def _transform(self, local_file_hash: str) -> energyweb.EnergyData:
        """
        Transforms the raw external energy data into blockchain format. Needs to be implemented for each different
        smart-contract and configuration type.
        """
        raw_energy, is_meter_down = self._fetch_remote_data(self.task_config.energy_meter)
        if not self.task_config.energy_meter.is_accumulated:
            last_remote_state = self.task_config.smart_contract.last_state()
            raw_energy.energy += last_remote_state[3] # get the fourth element returned from the contract from last_state: uint _lastSmartMeterReadWh
        raw_carbon_emitted, is_co2_down = self._fetch_remote_data(self.task_config.carbon_emission)
        calculated_co2 = raw_energy.energy * raw_carbon_emitted.accumulated_co2
        produced = {
            'value': int(raw_energy.energy),
            'is_meter_down': is_meter_down,
            'previous_hash': local_file_hash,
            'co2_saved': int(calculated_co2),
            'is_co2_down': is_co2_down
        }
        return energyweb.ProducedEnergy(**produced)


class CooConsumerTask(CooGeneralTask):

    def __init__(self, task_config: CooV1ConsumerConfiguration, polling_interval: datetime.timedelta,
                 queue: asyncio.Queue, store: str = None, enable_debug: bool = False):
        """
        :param task_config: Consumer configuration class instance
        :param polling_interval: Time interval between interrupts check
        :param queue: For thread safe messaging between tasks
        :param store: Path to folder where the log files will be stored in disk. DEFAULT won't store data in-disk.
        :param enable_debug: Enabling debug creates a log for errors. Needs storage. Please manually delete it.
        """
        super().__init__(task_config=task_config, polling_interval=polling_interval, store=store, queue=queue,
                         enable_debug=enable_debug)

    def _transform(self, local_file_hash: str) -> energyweb.EnergyData:
        """
        Transforms the raw external energy data into blockchain format. Needs to be implemented for each different
        smart-contract and configuration type.
        """
        raw_energy, is_meter_down = self._fetch_remote_data(self.task_config.energy_meter)
        if not self.task_config.energy_meter.is_accumulated:
            last_remote_state = self.task_config.smart_contract.last_state()
            raw_energy.energy += last_remote_state[3]
        consumed = {
            'value': int(raw_energy.energy),
            'is_meter_down': is_meter_down,
            'previous_hash': local_file_hash,
        }
        return energyweb.ConsumedEnergy(**consumed)
