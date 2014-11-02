import json
from requests import request
from functools import partial
from time import time, sleep


API_CALLS_WAITING_TIME = 0.05


class APICallException(Exception):
    def __init__(self, status_code, *args, **kwargs):
        self.status_code = status_code
        super(APICallException, self).__init__(*args, **kwargs)

    def __str__(self):
        return '%s - %s' % (self.status_code, super(APICallException, self).__str__())


class APICallerException(Exception):
    pass


class APICall(object):
    last_call = 0

    def __init__(self, token, url):
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Token %s' % token
        }

        def request_wrapper(func, *args, **kwargs):
            #wait between api calls
            sleep(max(0, self.__class__.last_call + API_CALLS_WAITING_TIME - time()))
            response = func(*args, **kwargs)
            self.__class__.last_call = time()
            if response.status_code >= 200 and response.status_code < 300:
                return response.status_code, response.json()
            else:
                raise APICallException(response.status_code, response.json())

        for method in ('get', 'post', 'put', 'delete', 'patch'):
            setattr(self, method, partial(request_wrapper, partial(request, method, url, headers=headers)))


class AttributesHiderMetaClass(type):
    def __new__(cls, name, bases, attrs):
        hide_attrs_attr = '_hide_attrs'
        hide_attrs = []
        for basecls in bases:
            hide_attrs.extend(getattr(basecls, hide_attrs_attr, []))
        hide_attrs.extend(attrs.get(hide_attrs_attr, []))
        attrs[hide_attrs_attr] = set(hide_attrs)
        return type.__new__(cls, name, bases, attrs)


class AttributesHider(object):
    __metaclass__ = AttributesHiderMetaClass
    def __new__(cls, *args, **kwargs):
        hide_attrs = getattr(cls, '_hide_attrs', ())
        for attr in hide_attrs:
            if hasattr(cls, attr):
                setattr(cls, '_%s' % attr, getattr(cls, attr))
        return super(AttributesHider, cls).__new__(cls, *args, **kwargs)


class APICaller(AttributesHider):
    _hide_attrs = ('url', 'callers')

    url = ''
    callers = []

    def __init__(self, token, url):
        if url:
            self._url = '%s%s' % (url, self._url)
        self._token = token
        self._call = APICall(self._token, self._url)
        for cls in self._callers:
            setattr(self,
                cls.__name__.lower(),
                cls(token, self._url)
            )


class APIRoot(APICaller):
    def __init__(self, token, url=''):
        if url:
            self._url = url
        super(APIRoot, self).__init__(token, '')


class APIObject(APICaller):
    _hide_attrs = ('lookup', 'fields')

    lookup = 'id'
    fields = []

    def __init__(self, token, url, attrs):
        lookup = attrs.get(self._lookup)
        self._url = '%s/' % lookup
        setattr(self, self._lookup, lookup)
        self._fill(attrs)
        super(APIObject, self).__init__(token, url)

    def _fill(self, attrs):
        for key, value in attrs.iteritems():
            if key in self._fields:
                setattr(self, key, value)

    def _create(self):
        self._call.post()

    def _retrieve(self):
        status_code, response = self._call.get()
        self._fill(response)

    def _update(self):
        self._call.patch()

    def _delete(self):
        self._call.delete()

    def __getattr__(self, name):
        if name not in self._fields:
            raise AttributeError
        self._retrieve()
        return getattr(self, name)

    def save(self):
        #TODO save
        pass

    def delete(self):
        #TODO delete
        pass


class APIList(APICaller):
    _hide_attrs = ('detail', 'results_key', 'count_key', 'next_url_key')

    detail = None
    results_key = 'results'
    count_key = 'count'
    next_url_key = 'next'

    def __init__(self, *args, **kwargs):
        self._count = None
        super(APIList, self).__init__(*args, **kwargs)
        self._next_url = self._url

    def __iter__(self):
        self._next_url = self._url
        self._results = []
        return self

    def _get(self):
        status_code, response = APICall(self._token, self._next_url).get()
        self._results = iter(response[self._results_key])
        self._count = response[self._count_key]
        self._next_url = response[self._next_url_key]

    def next(self):
        if self._results:
            try:
                return self._next_detail()
            except StopIteration:
                pass

        if not self._next_url:
            raise StopIteration

        self._get()

        return self._next_detail()

    def _next_detail(self):
        results = next(self._results)
        if self._detail:
            return self._detail(self._token, self._url, results)
        else:
            return results

    def __len__(self):
        if self._count is None:
            self._get()
        return self._count


class APIListDetail(APIList):
    def __init__(self, *args, **kwargs):
        if self._detail is None:
            raise APICallerException('Attribute detail have to be specified in class %s definition.' % self.__class__.__name__)
        super(APIListDetail, self).__init__(*args, **kwargs)

    def get(self, **kwargs):
        return self._detail(self._token, self._url, kwargs)

    def add(self, **kwargs):
        detail = self._detail(self._token, self._url, kwargs)
        detail.save()
        return detail
