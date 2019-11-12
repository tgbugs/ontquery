import os
import pytest
import rdflib
import ontquery as oq
import orthauth as oa

oa.utils.log.setLevel('DEBUG')
oq.utils.log.setLevel('DEBUG')
log = oq.utils.log.getChild('test')

try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
    from pyontutils import scigraph
    from pyontutils.config import auth as pauth
except ModuleNotFoundError:
    from ontquery.plugins.services import scigraph_client as scigraph
    from ontquery.plugins.namespaces.nifstd import CURIE_MAP

SKIP_NETWORK = ('SKIP_NETWORK' in os.environ or
                'FEATURES' in os.environ and 'network-sandbox' in os.environ['FEATURES'])
skipif_no_net = pytest.mark.skipif(SKIP_NETWORK, reason='Skipping due to network requirement')

oq.OntCuries(CURIE_MAP)

suffixes = (
        '',
        'hello',
        'world',
        'ev:il',
        '1234567',
        '1232/123123/asdfasdf',
        'lol_this#is/even-worse/_/123',
    )

test_graph = rdflib.Graph()
triples = (('UBERON:0000955', 'rdf:type', 'owl:Class'),
           ('UBERON:0000955', 'rdfs:label', 'brain'),
           ('UBERON:0000955', 'rdfs:subClassOf', 'owl:Thing'),
           ('BIRNLEX:796', 'rdf:type', 'owl:Class'),
           ('BIRNLEX:796', 'rdfs:label', 'Brain'),
)

for proto_t in triples:
    test_graph.add(rdflib.URIRef(oq.OntId(e)) if ':' in e else rdflib.Literal(e) for e in proto_t)

