import rdflib
import ontquery as oq
try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
except ModuleNotFoundError:
    from ontquery.plugins.namespaces import CURIE_MAP

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

