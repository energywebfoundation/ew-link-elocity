# Based on OCPP 1.6-JSON
import datetime
import uuid
from dataclasses import dataclass, field

from app.tasks.ocpp16.memorydao import Model


@dataclass
class Ocpp16:
    transactions: dict = field(default_factory=dict)
    req_queue: dict = field(default_factory=dict)
    res_queue: dict = field(default_factory=dict)

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
    class Tag:
        tag_id: str
        expiry_date: datetime.datetime

    def _answer(self, req: Request, body: dict):
        self.res_queue[req.msg_id] = Ocpp16.Response(req.msg_id, body)

    def _ask(self, verb: object, body: object):
        msg_id = str(uuid.uuid4())
        self.req_queue[msg_id] = Ocpp16.Request(msg_id, verb, body)

    def unlock_connector(self, connector_id):
        self._ask('UnlockConnector', {'connectorId': connector_id})

    def start_transaction(self, tag_id: str):
        self._ask('RemoteStartTransaction', {'connectorId': 1, 'idTag': tag_id})

    def stop_transaction(self, tx_id: int):
        self._ask('RemoteStopTransaction', {'transactionId': tx_id})

    def request_meter_values(self):
        self._ask('TriggerMessage', {'requestedMessage': 'MeterValues'})

    def _begin_transaction(self, conn_id: int, tag_id: str, timestamp: str, meter_start: int):
        @dataclass
        class Transaction:
            tx_id: int
            tag_id: str
            connector_id: int
            time_start: datetime.datetime
            meter_start: int
            time_end: datetime.datetime = None
            meter_stop: int = None

        tx_id = len(self.transactions) + 1
        time_start = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%Z')
        self.transactions[tx_id] = Transaction(tx_id, tag_id, conn_id, time_start, meter_start)
        return self.transactions[tx_id]

    def _end_transaction(self, tx_id: int, timestamp: str, meter_stop: int):
        time_end = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S%Z')
        tx = self.transactions[tx_id]
        tx.time_end = time_end
        tx.meter_stop = meter_stop
        return self.transactions[tx_id]

    def _handle_charging_station(self, serial_number: str, metadata: str):
        raise NotImplementedError

    def _handle_connector(self, number: int, last_status: str, meter_read=None, meter_unit=None, metadata=None):
        raise NotImplementedError

    def _authorize_tag(self, tag_id, expiry_date: datetime.datetime = None) -> Tag:
        raise NotImplementedError

    def _handle_wrong_answer(self, res: Response):
        raise NotImplementedError

    @staticmethod
    def handle_protocol(self, message: Request or Response):

        def remove_msg(res: Ocpp16.Response):
            del self.req_queue[res.req.msg_id]
            del self.res_queue[res.msg_id]

        if isinstance(message, Ocpp16.Response):
            response = message
            if response.req.typ in ('RemoteStartTransaction', 'RemoteStopTransaction','TriggerMessage'):
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
            if request.typ == 'BootNotification':
                self._handle_charging_station(request.body['chargePointSerialNumber'], metadata=request.body)
                self._answer(request, {'status': 'Accepted', 'currentTime': datetime.datetime.utcnow().isoformat(),
                                      'interval': 14400})
                return
            if request.typ == 'Authorize':
                tag = self._authorize_tag(request.body['idTag'])
                if tag:
                    self._answer(request,
                                 {'idTagInfo': {'status': 'Accepted', 'expiryDate': tag.expiry_date.isoformat()}})
                else:
                    self._answer(request, {'idTagInfo': {'status': 'Rejected'}})
                return
            if request.typ == 'StatusNotification':
                self._answer(request, {})
                self._handle_connector(number=request.body['connectorId'], last_status=request.body['info'])
                return
            if request.typ == 'MeterValues':
                self._answer(request, {})
                for value in request.body['meterValue']:
                    for sample in value['sampledValue']:
                        self._handle_connector(number=request.body['connectorId'], last_status=request.body['info'],
                                               meter_read=sample['value'], meter_unit=sample['unit'])
                        break
                    break
                return
            if request.typ == 'StartTransaction':
                tx = self._begin_transaction(conn_id=request.body['connectorId'], timestamp=request.body['timestamp'],
                                             meter_start=request.body['meterStart'], tag_id=request.body['idTag'])
                tag = self._authorize_tag(request.body['idTag'])
                if tag:
                    self._answer(request, {"transactionId": tx.tx_id,
                                       "idTagInfo": {"status": "Accepted", "expiryDate": tag.expiry_date}})
                else:
                    self._answer(request, {"transactionId": tx.tx_id, "idTagInfo": {"status": "Rejected"}})

                return
            if request.typ == 'StopTransaction':
                tx = self._end_transaction(tx_id=request.body['transactionId'], timestamp=request.body['timestamp'],
                                           meter_stop=request.body['meterStop'])


@dataclass
class ChargingStation(Model, Ocpp16):
    host: str
    port: int
    serial_number: str = None
    metadata: str = None
    connectors: dict = field(default_factory=dict)
    tags: [str] = field(default_factory=list)  # TODO: Use eth address as tag id
    last_heartbeat: dict = field(default_factory=dict)

    @property
    def reg_id(self) -> str:
        return f'{self.host}:{self.port}'

    @dataclass
    class Connector:
        connector_id: int
        last_status: str
        meter_read: str
        meter_unit: str
        metadata: str

    def _handle_charging_station(self, serial_number: str, metadata: str):
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
