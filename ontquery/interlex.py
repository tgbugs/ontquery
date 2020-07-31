# TEST InterLex endpoints
from ontquery.terms import OntTerm
from yarl import URL
import ontquery as oq
import os


def interlex_client(host: str = 'test3.scicrunch.org', scheme: str = 'https'):
    """ Direct InterLex API wrapper setup.



    :param host:
    :param scheme:
    :return:
    """
    InterLexRemote = oq.plugin.get('InterLex')
    api = URL(host)
    if not api.is_absolute():
        api = URL.build(scheme=scheme, host=host)
    api = api.with_path('api/1')
    ilx_cli = InterLexRemote(apiEndpoint=api)
    ilx_cli.setup(instrumented=OntTerm)
    return ilx_cli