import elasticsearch as es

from tasks.database import dao
from tasks.ocpp16.protocol import ChargingStation


class ElasticSearchDAO(dao.DAO):

    def __init__(self, id_att_name: str, cls_name: str, *service_urls: str):
        """
        :param id_att_name: Class id attribute name
        :param cls_name: Class name to be stored
        :param service_urls: i.e. 'http://localhost:9200', 'https://remotehost:9000'
        """
        self._index = id_att_name
        self._doc_type = cls_name
        self._db = es.Elasticsearch(service_urls)

    def create(self, obj: dao.Model):
        response = self._db.index(index=self._index, doc_type=self._doc_type, body=obj.to_dict(), id=obj.reg_id,
                                  refresh=True)
        if not response['result'] in ('created', 'updated'):
            raise es.ElasticsearchException('Fail creating or updating the object in the database')

    def retrieve(self, _id):
        self._db.indices.refresh(self._index)
        response = self._db.get(self._index, self._doc_type, id=_id)
        if not response['found']:
            raise es.ElasticsearchException('Object not found.')
        return response['_source']

    def retrieve_all(self):
        self._db.indices.refresh(self._index)
        response = self._db.search(self._index, self._doc_type, body={"query": {"match_all": {}}})
        return [hit["_source"] for hit in response['hits']['hits']]

    def update(self, obj: dao.Model):
        self.create(obj)

    def delete(self, obj: dao.Model):
        response = self._db.delete(index=self._index, doc_type=self._doc_type, id=obj.reg_id)
        if not response['result'] == 'deleted':
            raise es.ElasticsearchException('Object not found.')

    def find_by(self, attributes: dict) -> [dict]:
        self._db.indices.refresh(self._index)
        res = self._db.search(self._index, self._doc_type, body={"query": {"bool": {"must": [{"match": attributes}]}}})
        return [hit["_source"] for hit in res['hits']['hits']]

    def delete_all(self):
        self._db.delete_by_query(self._index, doc_type=self._doc_type, body={"query": {"match_all": {}}})

    def delete_unidentified(self):
        self._db.delete_by_query(self._index, doc_type=self._doc_type,
                                 body={"bool": {"must_not": {"exists": {"field": "reg_id"}}}})

    def query(self, attributes: dict) -> [dict]:
        """
        :param attributes: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/query-filter-context.html
        :return: dict
        """
        self._db.indices.refresh(self._index)
        res = self._db.search(self._index, self._doc_type, body={"query": attributes})
        return [hit["_source"] for hit in res['hits']['hits']]


class ElasticSearchDAOFactory(dao.DAOFactory):

    def __init__(self, index_name: str, *service_urls: str):
        super().__init__()
        self._instances = {}
        self._service_urls = service_urls
        self._index = index_name

    def get_instance(self, cls) -> ElasticSearchDAO:
        if id(cls) in list(self._instances.keys()):
            return self._instances[id(cls)]
        self._instances[id(cls)] = ElasticSearchDAO(self._index, cls.__name__, *self._service_urls)
        return self._instances[id(cls)]


if __name__ == '__main__':
    factory = ElasticSearchDAOFactory('elocity', 'http://127.0.0.1:9200', 'http://0.0.0.0:9200')
    cs_dao = factory.get_instance(ChargingStation)
    cs0 = ChargingStation(host='localhost', port=8080)
    cs0.serial_number = '111'
    cs1 = ChargingStation(host='localhost', port=8081)
    cs1.serial_number = '222'
    cs2 = ChargingStation(host='localhost', port=8082)
    try:
        cs_dao.delete_all()
    except:
        pass
    finally:
        print('DB is clean.')
    try:
        [cs_dao.create(cs) for cs in [cs0, cs1, cs2]]
        print(f'{cs_dao.retrieve_all()}')
        print(f"{cs_dao.retrieve('111')}")
        cs_dao.delete(cs1)
        print(f'{cs_dao.retrieve_all()}')
        cs0.port = '8090'
        cs_dao.update(cs0)
        print(f'{cs_dao.retrieve_all()}')
        query = {"bool": {"must": [{"match": {"port": "8090"}}]}}
        print(f'{cs_dao.find_by(query)}')
        cs_dao.delete_all()
    except es.ElasticsearchException as e:
        print(f'Failed because elastic search said: {e.with_traceback(e.__traceback__)}')
    except Exception as e:
        print(f'Failed because: {e.with_traceback(e.__traceback__)}')
