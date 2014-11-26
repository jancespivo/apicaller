from requests import request
from functools import partial
from time import time, sleep


API_CALLS_WAITING_TIME = 0.05


class APICallException(Exception):
    def __init__(self, response, *args, **kwargs):
        self.response = response
        super(APICallException, self).__init__(*args, **kwargs)

    def get_response_data(self):
        try:
            return self.response.json()
        except Exception:
            return self.response.text

    def __str__(self):
        return '%s - %s' % (self.response.status_code, len(self.response.content))


class APICallerException(Exception):
    #TODO avoid, replace this
    pass


class APICall(object):
    """
    abstraction to http calls
    """
    last_call = 0

    def __init__(self, url, token='', json=True, verify_ssl=True):
        headers = {}
        if token:
            headers.update({
                'Authorization': 'Token %s' % token
            })

        def request_wrapper(func, data={}):
            #wait between api calls
            sleep(max(0, self.__class__.last_call + API_CALLS_WAITING_TIME - time()))
            kwargs = {}
            if data:
                if json:
                    kwargs['json'] = data
                else:
                    kwargs['data'] = data
            response = func(**kwargs)

            self.__class__.last_call = time()

            if json:
                try:
                    response_data = response.json()
                except Exception:
                    raise APICallException(response)
            else:
                response_data = response.text

            if 200 <= response.status_code < 300:
                return response.status_code, response_data
            else:
                raise APICallException(response)

        for method in ('get', 'post', 'put', 'delete', 'patch'):
            setattr(
                self,
                method,
                partial(request_wrapper, partial(request, method, url, headers=headers, verify=verify_ssl))
            )


class AttributesHiderMetaClass(type):
    """
    gather _hide_attrs class attribute from all bases
    """
    def __new__(cls, name, bases, attrs):
        hide_attrs_attr = '_hide_attrs'
        hide_attrs = []
        for basecls in bases:
            hide_attrs.extend(getattr(basecls, hide_attrs_attr, []))
        hide_attrs.extend(attrs.get(hide_attrs_attr, []))
        attrs[hide_attrs_attr] = set(hide_attrs)
        return type.__new__(cls, name, bases, attrs)


class AttributesHider(object):
    """
    perform the hiding of attributes (actually protect them with _)
    """
    __metaclass__ = AttributesHiderMetaClass

    def __new__(cls, *args, **kwargs):
        hide_attrs = getattr(cls, '_hide_attrs', ())
        for attr in hide_attrs:
            if hasattr(cls, attr):
                setattr(cls, '_%s' % attr, getattr(cls, attr))
        return super(AttributesHider, cls).__new__(cls, *args, **kwargs)


class APINode(AttributesHider):
    """
    generic api url and nodes holder
    """
    _hide_attrs = ('url', 'nodes', 'name')

    url = ''
    nodes = []
    name = ''

    def __init__(self, url, token='', json=True, verify_ssl=True):
        if url:
            self._url = '%s%s' % (url, self._url)

        self._call = APICall(self._url, token=token, json=json, verify_ssl=verify_ssl)
        for cls in self._nodes:
            setattr(
                self,
                cls.name or cls.__name__.lower(),
                cls(self._url, token=token, json=json, verify_ssl=verify_ssl)
            )


class APIRoot(APINode):
    def __init__(self, url, **kwargs):
        if url:
            self._url = url
        super(APIRoot, self).__init__('', **kwargs)


class APIObject(APINode):
    _hide_attrs = ('lookup', 'fields')

    lookup = 'id'
    fields = []

    def __init__(self, url, attrs, **kwargs):
        lookup = attrs.get(self._lookup)
        self._url = '%s/' % lookup
        setattr(self, self._lookup, lookup)
        self._fill(attrs)
        super(APIObject, self).__init__(url, **kwargs)

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


class APIList(APINode):
    _hide_attrs = ('detail', 'results_key', 'count_key', 'next_url_key')

    detail = None
    results_key = 'results'
    count_key = 'count'
    next_url_key = 'next'

    def __init__(self, url, **kwargs):
        self._count = None
        super(APIList, self).__init__(url, **kwargs)
        self._kwargs = kwargs
        self._next_url = self._url

    def __iter__(self):
        self._next_url = self._url
        self._results = []
        return self

    def _get(self):
        status_code, response = APICall(self._next_url, **self._kwargs).get()
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
            return self._detail(self._url, results, **self._kwargs)
        else:
            return results

    def __len__(self):
        if self._count is None:
            self._get()
        return self._count


class APIListDetail(APIList):
    def __init__(self, url, **kwargs):
        if self._detail is None:
            raise APICallerException('Attribute detail have to be specified in class %s definition.' % self.__class__.__name__)
        super(APIListDetail, self).__init__(url, **kwargs)

    def get(self, **kwargs):
        return self._detail(self._url, **self._kwargs)

    def add(self, **kwargs):
        detail = self._detail(self._url, **self._kwargs)
        detail.save()
        return detail
