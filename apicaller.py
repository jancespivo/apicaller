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


class APICaller(object):
    api_url = ''
    api_callers = []

    def __init__(self, token, url):
        if url:
            self.api_url = '%s%s' % (url, self.api_url)
        self.token = token
        self._call = APICall(self.token, self.api_url)
        for cls in self.api_callers:
            setattr(self,
                cls.__name__.lower(),
                cls(token, self.api_url)
            )


class APIRootCaller(APICaller):
    def __init__(self, token, url=''):
        if url:
            self.api_url = url
        super(APIRootCaller, self).__init__(token, '')


class APIDetail(APICaller):
    api_lookup = 'id'
    api_fields = []

    def __init__(self, token, url, attrs):
        lookup = attrs.get(self.api_lookup)
        self.api_url = '%s/' % lookup
        setattr(self, self.api_lookup, lookup)
        self._fill(attrs)
        super(APIDetail, self).__init__(token, url)

    def _fill(self, attrs):
        for key, value in attrs.iteritems():
            if key in self.api_fields:
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
        if name not in self.api_fields:
            raise AttributeError
        self._retrieve()
        return getattr(self, name)


class APIListCaller(APICaller):
    api_detail = None
    api_results_key = 'results'
    api_count_key = 'count'
    api_next_url_key = 'next'

    def __init__(self, *args, **kwargs):
        self._count = None
        super(APIListCaller, self).__init__(*args, **kwargs)
        self._next_url = self.api_url

    def __iter__(self):
        self._next_url = self.api_url
        self._results = []
        return self

    def _get(self):
        status_code, response = APICall(self.token, self._next_url).get()
        self._results = iter(response[self.api_results_key])
        self._count = response[self.api_count_key]
        self._next_url = response[self.api_next_url_key]

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
        if self.api_detail:
            return self.api_detail(self.token, self.api_url, results)
        else:
            return results

    def __len__(self):
        if self._count is None:
            self._get()
        return self._count


class APIListDetailCaller(APIListCaller):
    def __init__(self, *args, **kwargs):
        if self.api_detail is None:
            raise APICallerException('Attribute api_detail have to be specified in class %s definition.' % self.__class__.__name__)
        super(APIListDetailCaller, self).__init__(*args, **kwargs)

    def retrieve(self, **kwargs):
        return self.api_detail(self.token, self.api_url, kwargs)
