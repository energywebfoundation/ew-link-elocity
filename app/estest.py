#!/usr/bin/env python3

import uuid
from datetime import datetime
from elasticsearch import Elasticsearch
es = Elasticsearch('http://10.10.1.162:9200')


def write():

    connector1 = {
        'connector_id': 'c9d342c6-b141-4d95-9e13-2f50f7bdc3c6',
        'last_status': 'good',
        'meter_read': '1',
        'meter_unit': 'kWH',
        'metadata': 'First connector'
    }

    connector2 = {
        'connector_id': 'c9d342c6-b141-4d95-9e13-2f50f7bdc3c6',
        'last_status': 'bad',
        'meter_read': '2',
        'meter_unit': 'kWH',
        'metadata': 'Second connector'
    }

    connector3 = {
        'connector_id': '748c82bd-b7f5-4262-978b-e62dacf34b6e',
        'last_status': 'bad',
        'meter_read': '2',
        'meter_unit': 'kWH',
        'metadata': 'Second connector'
    }

    connectors = [
        connector1,
        connector2,
        connector3
    ]

    doc = {
        'serial_number': '06107648-758e-45b8-a159-762914d369f5',
        'metadata': 'I\'m a better station',
        'connectors': connectors
    }
    res = es.index(index="asset", doc_type='chargingstation', id=1, body=doc)
    print(res['result'])

def read():
    res = es.get(index="asset", doc_type='chargingstation', id=1)
    print(res['_source'])

def refresh():
    es.indices.refresh(index="asset")

def search():
    res = es.search(index="asset", body={"query": {"match_all": {}}})
    print("Got %d Hits:" % res['hits']['total'])
    for hit in res['hits']['hits']:
        print("%(serial_number)s: %(metadata)s %(connectors)s" % hit["_source"])

search()