import json
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class InterlexSession:
    """ Boiler plate for SciCrunch server responses. """

    class Error(Exception):
        """Script could not complete."""

    class NoApiKeyError(Error):
        """ No api key has been set """

    class IncorrectAPIKeyError(Error):
        """Incorrect API key for scicrunch website used."""

    def __init__(self,
                 key: str,
                 host: str = 'test3.scicrunch.org', # MAIN TEST -> test3.scicrunch.org
                 auth: tuple = ('', ''), # user, password for authentication
                 retries: int = 3, # retries if code in status_forcelist
                 backoff_factor: float = 1.0, # delay factor for reties
                 status_forcelist: tuple = (400, 500, 502, 504), # flagged codes for retry
                 ) -> None:
        """ Initialize Session with SciCrunch Server.

        :param str key: API key for SciCrunch [should work for test hosts].
        :param str host: Base url for hosting server [can take localhost:8080].
        """
        self.key = key
        self.host = ''
        self.api = ''

        # Pull host for potential url
        if host.startswith('http'):
            host = urlparse(host).netloc

        # Use host to create api url
        if host.startswith('localhost'):
            self.host = "http://" + host
            self.api = self.host + '/api/1/'
        else:
            self.host = "https://" + host
            self.api = self.host + '/api/1/'

        # Api key check
        if self.key is None:  # injected by orthauth
            # Error here because viewing without a key handled in InterLexRemote not here
            raise self.NoApiKeyError('You have not set an API key for the SciCrunch API!')
        if not requests.get(self.api+'user/info', params={'key':self.key}).status_code in [200, 201]:
            raise self.IncorrectAPIKeyError(f'api_key given is incorrect.')

        self.session = requests.Session()
        self.session.auth = auth
        self.session.headers.update({'Content-type': 'application/json'})
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist, # 400 for no ILX ID generated.
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def __session_shortcut(self, endpoint: str, data: dict, session_type: str = 'GET') -> dict:
        """ Short for both GET and POST.

        Will only crash if success is False or if there a 400+ error.
        """
        def _prepare_data(data: dict) -> dict:
            """ Check if request data inputed has key and proper format. """
            if data is None:
                data = {'key': self.key}
            elif isinstance(data, dict):
                data.update({'key': self.key})
            else:
                raise ValueError('request session data must be of type dictionary')
            return json.dumps(data)

        # urljoin bug; .com/ap1/1/ + /test/ != .com/ap1/1/test/ but .com/test/
        # HOWEVER .com/ap1/1/ + test/ == .com/ap1/1/test/
        endpoint = endpoint[1:] if endpoint.startswith('/') else endpoint
        url = urljoin(self.api, endpoint)
        if data:
            for key, value in data.items():
                url = url.format(**{key:value})
        data = _prepare_data(data)
        try:
            # TODO: Could use a Request here to shorten code.
            if session_type == 'GET':
                response = self.session.get(url, data=data)
            else:
                response = self.session.post(url, data=data)
            if response.json()['success'] == False:
                # BUG: Need to retry if server fails to create the ILX ID.
                # if response.json().get('errormsg') == 'could not generate ILX identifier':
                #     return response.json()
                raise ValueError(response.text + f' -> STATUS CODE: {response.status_code} @ URL: {response.url}')
            response.raise_for_status()
        # crashes if the server couldn't use it or it never made it.
        except:
            raise requests.exceptions.HTTPError(f'{response.text} {response.status_code}')

        # response.json() == {'data':{}, 'success':bool}
        return response.json()['data']

    def _get(self, endpoint: str, data: dict = None) -> dict:
        """ Quick GET for SciCrunch. """
        return self.__session_shortcut(endpoint, data, 'GET')

    def _post(self, endpoint: str , data: dict = None) -> dict:
        """ Quick POST for SciCrunch. """
        return self.__session_shortcut(endpoint, data, 'POST')
