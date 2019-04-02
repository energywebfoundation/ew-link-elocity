import abc
import energyweb


class Model(energyweb.Serializable):
    """ MVC Concrete Model """

    def __init__(self, reg_id=None):
        """
        :param reg_id: Registry ID
        :return:
        """
        self.reg_id = reg_id

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.reg_id == other.reg_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self.reg_id is None:
            raise AssertionError('Object is not in sync with the object in db session.')
        return hash(''.join(dir(self))) ^ hash(self.reg_id)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.reg_id)

    def __self__(self):
        return self


class ABCSingleton(abc.ABCMeta):
    instance = None

    def __call__(cls, *args, **kw):
        if not cls.instance:
            cls.instance = super().__call__(*args, **kw)
        return cls.instance


class DAO(metaclass=abc.ABCMeta):
    """
    Data Access Object is an Abstract Class
    Must be initialized using 'DAO.register(<DAO>)'
    """

    @abc.abstractmethod
    def create(self, obj): pass

    @abc.abstractmethod
    def retrieve(self, _id): pass

    @abc.abstractmethod
    def retrieve_all(self): pass

    @abc.abstractmethod
    def update(self, obj): pass

    @abc.abstractmethod
    def delete(self, obj): pass

    @abc.abstractmethod
    def find_by(self, attributes: dict): pass


class DAOSingleton(metaclass=ABCSingleton):
    """
    Data Access Object is an Abstract Class
    Must be initialized using 'DAO.register(<DAO>)'
    """

    @abc.abstractmethod
    def create(self, obj): pass

    @abc.abstractmethod
    def retrieve(self, _id): pass

    @abc.abstractmethod
    def retrieve_all(self): pass

    @abc.abstractmethod
    def update(self, obj): pass

    @abc.abstractmethod
    def delete(self, obj): pass

    @abc.abstractmethod
    def find_by(self, attributes: dict): pass


class DAOFactory(metaclass=ABCSingleton):

    @abc.abstractmethod
    def __init__(self): pass

    @abc.abstractmethod
    def get_instance(self, cls): pass


class DAOI(DAO):
    """
    Generic interface for all DAO implementations
    This class garantees an interface between data objects and odbcs or orms connectors
    """

    def __init__(self, dao):
        if not isinstance(dao, DAO):
            raise
        self._dao = dao

    def create(self, obj):
        if not isinstance(obj, Model):
            raise
        return self._dao.create(obj)

    def retrieve(self, _id=None) -> object:
        return self._dao.retrieve(_id)

    def retrieve_all(self) -> list:
        return self._dao.retrieve_all()

    def update(self, obj):
        if not isinstance(obj, Model):
            raise
        return self._dao.update(obj)

    def delete(self, obj):
        if not isinstance(obj, Model):
            raise
        return self._dao.delete(obj)
