# Based on OCPP 1.6-JSON
import datetime
import uuid
from dataclasses import dataclass, field

from tasks.database import dao


@dataclass
class Ocpp16:
    transactions: dict = field(default_factory=dict)
    req_queue: dict = field(default_factory=dict)
    res_queue: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)

    @dataclass
    class Request:
        msg_type: int
        msg_id: str
        typ: str
        body: dict
        is_pending: bool = True

        def serialize(self):
            msg = [self.msg_type, self.msg_id, self.typ, self.body]
            return msg

    @dataclass
    class Response:
        msg_type: int
        msg_id: str
        body: dict
        is_pending: bool = True
        req: object = None

        def serialize(self):
            msg = [self.msg_type, self.msg_id, self.body]
            return msg

    @dataclass
    class Tag(dao.Model):
        tag_id: str
        expiry_date: datetime.datetime

        @staticmethod
        def from_dict(obj_dict):
            obj_dict['expiry_date'] = datetime.datetime.fromisoformat(obj_dict['expiry_date'])
            return Ocpp16.Tag(**obj_dict)

    @dataclass
    class Transaction(dao.Model):
        tx_id: int
        tag_id: str
        connector_id: int
        time_start: datetime.datetime
        meter_start: int
        time_end: datetime.datetime = None
        meter_stop: int = None

        @staticmethod
        def from_dict(obj_dict):
            obj_dict['time_start'] = datetime.datetime.fromisoformat(obj_dict['time_start'])
            obj_dict['time_end'] = datetime.datetime.fromisoformat(obj_dict['time_end']) \
                if 'time_end' in obj_dict and obj_dict['time_end'] else None
            return Ocpp16.Transaction(**obj_dict)

    def _answer(self, req: Request, body: dict):
        self.res_queue[req.msg_id] = Ocpp16.Response(3, req.msg_id, body)

    def _ask(self, typ: str, body: dict):
        msg_id = str(uuid.uuid4())
        self.req_queue[msg_id] = Ocpp16.Request(2, msg_id, typ, body)

    def unlock_connector(self, connector_id):
        self._ask('UnlockConnector', {'connectorId': connector_id})

    def start_transaction(self, tag_id: str):
        self._ask('RemoteStartTransaction', {'connectorId': 1, 'idTag': str(tag_id)})

    def stop_transaction(self, tx_id: int):
        self._ask('RemoteStopTransaction', {'transactionId': int(tx_id)})

    def request_meter_values(self):
        self._ask('TriggerMessage', {'requestedMessage': 'MeterValues'})

    def _register_tx_start(self, conn_id: int, tag_id: str, timestamp: str, meter_start: int):
        tx_id = len(self.transactions) + 1
        time_start = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
        self.transactions[tx_id] = Ocpp16.Transaction(tx_id, tag_id, conn_id, time_start, meter_start)
        return self.transactions[tx_id]

    def _register_tx_stop(self, tx_id: int, timestamp: str, meter_stop: int, tag_id: str, tx_data: list):
        time_end = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
        if tx_id not in self.transactions:
            tx = Ocpp16.Transaction(tx_id, tag_id, 0, datetime.datetime.now(), 0, time_end, meter_stop)
            samples = []
            [samples.extend([(sample, data['timestamp']) for sample in data['sampledValue']]) for data in tx_data]
            for sample, timestamp in samples:
                if sample['context'] == 'Transaction.Begin':
                    tx.meter_start = sample['value']
                    tx.time_start = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
                    break
            self.transactions[tx_id] = tx
        else:
            self.transactions[tx_id].time_end = time_end
            self.transactions[tx_id].meter_stop = meter_stop
        return self.transactions[tx_id]

    def _handle_charging_station(self, serial_number: str, metadata: dict):
        """
        Implement to add historical data and persistence.
        :param serial_number: Works as an fixed id, once the ip number may vary.
        :param metadata: Other metadata like manufacturer name.
        """
        raise NotImplementedError

    def _handle_connector(self, number: int, last_status: str, meter_read=None, meter_unit=None, metadata=None):
        """
        Implement to add historical data and persistence.
        :param number: Connector number on the charging station. Parse serial_number from metadata for fixed id.
        :param last_status: Connector status - Starting, Finishing, Error.
        :param meter_read: Measured energy value.
        :param meter_unit: Unit of measured energy. Default is Watt-hour.
        :param metadata: Connector metadata like manufacturer name and serial number.
        """
        raise NotImplementedError

    def _authorize_tag(self, tag_id, expiry_date: datetime.datetime = None) -> Tag:
        """
        Implement to add the access control logic to your application, like querying a remote service or database.
        """
        raise NotImplementedError

    def _handle_wrong_answer(self, res: Response):
        """
        Implement to add the error handling logic to your application.
        """
        raise NotImplementedError

    def follow_protocol(self, message: Request or Response):

        def remove_msg(res: Ocpp16.Response):
            del self.req_queue[res.req.msg_id]
            del self.res_queue[res.msg_id]

        if isinstance(message, Ocpp16.Response):
            response = message
            if response.req.typ in ('RemoteStartTransaction', 'RemoteStopTransaction', 'TriggerMessage'):
                if response.body['status'] != 'Accepted':
                    self._handle_wrong_answer(response)
            elif response.req.typ == 'UnlockConnector':
                if response.body['status'] != 'Unlocked':
                    self._handle_wrong_answer(response)
            remove_msg(response)
            return

        elif isinstance(message, Ocpp16.Request):

            request = message
            if request.typ == 'Heartbeat':
                self._answer(request, {'currentTime': datetime.datetime.utcnow().isoformat()})
                return
            elif request.typ == 'BootNotification':
                self._handle_charging_station(request.body['chargeBoxSerialNumber'], metadata=request.body)
                self._answer(request, {'status': 'Accepted', 'currentTime': datetime.datetime.utcnow().isoformat(),
                                       'interval': 14400})
                return
            elif request.typ == 'Authorize':
                tag = self._authorize_tag(request.body['idTag'])
                if tag:
                    self._answer(request,
                                 {'idTagInfo': {'status': 'Accepted', 'expiryDate': tag.expiry_date.isoformat()}})
                else:
                    self._answer(request, {'idTagInfo': {'status': 'Rejected'}})
            elif request.typ == 'StatusNotification':
                self._answer(request, {})
                self._handle_connector(number=request.body['connectorId'], last_status=request.body['info'])
            elif request.typ == 'MeterValues':
                self._answer(request, {})
                for value in request.body['meterValue']:
                    for sample in value['sampledValue']:
                        self._handle_connector(number=request.body['connectorId'], last_status=request.body['info'],
                                               meter_read=sample['value'], meter_unit=sample['unit'])
                        break
                    break
            elif request.typ == 'StartTransaction':
                tx = self._register_tx_start(conn_id=request.body['connectorId'], timestamp=request.body['timestamp'],
                                             meter_start=request.body['meterStart'], tag_id=request.body['idTag'])
                tag = self._authorize_tag(request.body['idTag'])
                if tag:
                    self._answer(request, {"transactionId": tx.tx_id, "idTagInfo": {"status": "Accepted",
                                                                                    "expiryDate": tag.expiry_date.isoformat()}})
                else:
                    self._answer(request, {"transactionId": tx.tx_id, "idTagInfo": {"status": "Rejected"}})

            elif request.typ == 'StopTransaction':
                tx = self._register_tx_stop(tx_id=request.body['transactionId'], timestamp=request.body['timestamp'],
                                            meter_stop=request.body['meterStop'], tag_id=request.body['idTag'],
                                            tx_data=request.body['transactionData'])
                tag = self._authorize_tag(request.body['idTag'])
                if tag:
                    self._answer(request, {"transactionId": tx.tx_id, "idTagInfo": {"status": "Accepted",
                                                                                    "expiryDate": tag.expiry_date.isoformat()}})
                else:
                    self._answer(request, {"transactionId": tx.tx_id, "idTagInfo": {"status": "Rejected"}})
            else:
                print(f"Unknown Request: {request.serialize()}")


class ChargingStation(dao.Model, Ocpp16):

    def __init__(self, host: str, port: int, reg_id: str, last_seen: datetime.datetime = None, metadata: dict = None,
                 serial_number: str = None, connectors: dict = None, last_heartbeat: dict = None,
                 transactions: dict = None,
                 tags: dict = None):
        self.host = host
        self.port = port
        self.last_seen: last_seen if last_seen else datetime.datetime = datetime.datetime.now()
        self.metadata = metadata if metadata else {}
        self.serial_number = serial_number if serial_number else None
        self.connectors = connectors if connectors else {}
        self.last_heartbeat = last_heartbeat if last_heartbeat else None
        dao.Model.__init__(self, reg_id=reg_id)
        Ocpp16.__init__(self)
        self.transactions = transactions if transactions else {}
        self.tags = tags if tags else {}

    @dataclass
    class Connector(dao.Model):
        connector_id: int
        last_status: str
        meter_read: str
        meter_unit: str
        metadata: dict

        @staticmethod
        def from_dict(obj_dict: dict):
            return ChargingStation.Connector(**obj_dict)

    def _handle_charging_station(self, serial_number: str, metadata: dict):
        self.serial_number = serial_number
        self.metadata = metadata

    def _handle_connector(self, number: int, last_status: str, meter_read=None, meter_unit=None, metadata=None):
        if number not in self.connectors:
            self.connectors[number] = ChargingStation.Connector(number, last_status, meter_read, meter_unit, metadata)
        else:
            connector = self.connectors[number]
            connector.last_status = last_status
            if meter_read:
                connector.meter_read = meter_read
                connector.meter_unit = meter_unit
        return self.connectors[number]

    def _authorize_tag(self, tag_id, expiry_date: datetime.datetime = None):
        if tag_id not in self.tags:
            if not expiry_date:
                expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=360)
            self.tags[tag_id] = ChargingStation.Tag(tag_id, expiry_date)
        return self.tags[tag_id]

    def _handle_wrong_answer(self, res: Ocpp16.Response):
        print(f'Request {res.serialize()} rejected')

    def to_dict(self):
        dict_obj = super().to_dict()
        dict_obj['reg_id'] = self.reg_id
        dict_obj['req_queue'] = None
        dict_obj['res_queue'] = None
        del dict_obj['req_queue']
        del dict_obj['res_queue']
        return dict_obj

    @staticmethod
    def from_dict(obj_dict: dict):
        obj_dict['last_seen'] = datetime.datetime.fromisoformat(obj_dict['last_seen']) \
            if 'last_seen' in obj_dict else None
        obj_dict['connectors'] = {k: ChargingStation.Connector.from_dict(v) for k, v in obj_dict['connectors'].items()} \
            if 'connectors' in obj_dict else {}
        obj_dict['transactions'] = {k: Ocpp16.Transaction.from_dict(v) for k, v in obj_dict['transactions'].items()} \
            if 'transactions' in obj_dict else {}
        obj_dict['tags'] = {k: Ocpp16.Tag.from_dict(v) for k, v in obj_dict['tags'].items()} \
            if 'tags' in obj_dict else {}
        return ChargingStation(**obj_dict)
