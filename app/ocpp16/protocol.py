# Based on OCPP 1.6-JSON
import datetime
import uuid
from dataclasses import dataclass, field

from app.ocpp16.memorydao import MemoryDAOFactory, Model

FACTORY = MemoryDAOFactory()


@dataclass
class Request:
    msg_type: int
    msg_id: str
    typ: str
    body: dict

    def serialize(self):
        msg = [self.msg_type, self.msg_id, self.typ, self.body]
        return msg


@dataclass
class Response:
    msg_type: int
    msg_id: str
    body: dict
    req: Request = None

    def serialize(self):
        msg = [self.msg_type, self.msg_id, self.body]
        return msg


@dataclass
class OcppChargingStation(Model):
    host: str
    port: int
    serial_number: str = None
    metadata: str = None
    req_queue: dict = field(default_factory=dict)
    res_queue: dict = field(default_factory=dict)
    connectors: dict = field(default_factory=dict)
    transactions: dict = field(default_factory=dict)
    tags: [str] = field(default_factory=list)  # TODO: Use eth address as tag id
    last_heartbeat: dict = None
    reg_id = f'{host}:{port}'

    def _answer(self, req: Request, body: dict):
        self.res_queue[req.msg_id] = Response(req.msg_id, body)

    def _ask(self, verb: object, body: object):
        msg_id = str(uuid.uuid4())
        self.req_queue[msg_id] = Request(msg_id, verb, body)

    def _add_connector(self, number: int, last_status: str, meter_read=None, meter_unit=None):
        @dataclass
        class Connector:
            connector_id: int
            last_status: str
            meter_read: str
            meter_unit: str

        if number not in self.connectors:
            self.connectors[number] = Connector(number, last_status, meter_read, meter_unit)
        else:
            connector = self.connectors[number]
            connector.last_status = last_status
            if meter_read:
                connector.meter_read = meter_read
                connector.meter_unit = meter_unit
        return self.connectors[number]

    def _add_tag(self, tag_id, expiry_date: datetime.datetime = None):
        @dataclass
        class Tag:
            tag_id: str
            expiry_date: datetime.datetime

        if not expiry_date:
            expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=360)
        self.tags[tag_id] = Tag(tag_id, expiry_date)
        return self.tags[tag_id]

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

    def unlock_connector(self, connector_id):
        self._ask('UnlockConnector', {'connectorId': connector_id})

    def start_transaction(self, tag_id: str):
        self._ask('RemoteStartTransaction', {'connectorId': 1, 'idTag': tag_id})

    def stop_transaction(self, tx_id: int):
        self._ask('RemoteStopTransaction', {'transactionId': tx_id})

    def request_meter_values(self):
        self._ask('TriggerMessage', {'requestedMessage': 'MeterValues'})

    @staticmethod
    def follow_protocol(self, message: Request or Response):

        def check_right_answer(res: Response, status: str):
            if res.body['status'] != status:
                return
            else:
                print(f'Request {res.serialize()} failed')
                raise Exception('Request failed, please check Charging Station.')

        if isinstance(message, Response):
            response = message
            if response.req.typ in ('UnlockConnector', 'RemoteStartTransaction', 'RemoteStopTransaction',
                                    'TriggerMessage'):
                check_right_answer(response, 'Accepted')
                return

        elif isinstance(message, Request):

            request = message
            if request.typ == 'Heartbeat':
                self._answer(request, {'currentTime': datetime.datetime.utcnow().isoformat()})
                return
            if request.typ == 'BootNotification':
                self.metadata = request.body
                self.serial_number = request.body['chargePointSerialNumber']
                self._answer(request, {'status': 'Accepted',
                                      'currentTime': datetime.datetime.utcnow().isoformat(),
                                      'interval': 14400})
                return
            if request.typ == 'Authorize':
                if request.body['idTag'] in self.tags:
                    tag = self.tags[request.body['idTag']]
                    self._answer(request,
                                 {'idTagInfo': {'status': 'Accepted', 'expiryDate': tag.expiry_date.isoformat()}})
                else:
                    self._answer(request, {'idTagInfo': {'status': 'Rejected'}})
                return
            if request.typ == 'StatusNotification':
                self._answer(request, {})
                self._add_connector(number=request.body['connectorId'], last_status=request.body['info'])
                return
            if request.typ == 'MeterValues':
                self._answer(request, {})
                for value in request.body['meterValue']:
                    for sample in value['sampledValue']:
                        meter_read = sample['value']
                        meter_unit = sample['unit']
                        self._add_connector(number=request.body['connectorId'], last_status=request.body['info'],
                                            meter_read=meter_read, meter_unit=meter_unit)
                        break
                    break
                return
            if request.typ == 'StartTransaction':
                tx = self._begin_transaction(conn_id=request.body['connectorId'], timestamp=request.body['timestamp'],
                                             meter_start=request.body['meterStart'], tag_id=request.body['idTag'])
                tag = self.tags[request.body['idTag']]
                self._answer(request, {"transactionId": tx.tx_id,
                                      "idTagInfo": {"status": "Accepted", "expiryDate": tag.expiry_date}})
                return
            if request.typ == 'StopTransaction':
                tx = self._end_transaction(tx_id=request.body['transactionId'], timestamp=request.body['timestamp'],
                                           meter_stop=request.body['meterStop'])


stateful_cs = FACTORY.get_instance(OcppChargingStation)


def dispatcher(cs: OcppChargingStation, incoming: Request or Response):
    cs = stateful_cs.persist(cs)
    if isinstance(incoming, Response):
        if incoming.msg_id not in cs.req_queue:
            raise ConnectionError('Out-of-sync: Response for an unsent message.')
        incoming.req = cs.req_queue[incoming.msg_id]
    cs.follow_protocol(message=incoming)
    stateful_cs.update(cs)


def aggregator() -> [Request or Response]:
    requests, responses = [], []
    requests = [requests + cs.req_queue for cs in stateful_cs.retrieve_all()]
    responses = [responses + cs.res_queue for cs in stateful_cs.retrieve_all()]
    return responses + requests
