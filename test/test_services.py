import os
import unittest
import rdflib
import ontquery as oq

# FIXME TODO per service ... + mismatch warning
oq.OntCuries({'rdf': str(rdflib.RDF),
              'rdfs': str(rdflib.RDFS),
              'owl': str(rdflib.OWL),
              'BFO': 'http://purl.obolibrary.org/obo/BFO_',
              'UBERON': 'http://purl.obolibrary.org/obo/UBERON_',
              'NLX': 'http://uri.neuinfo.org/nif/nifstd/nlx_',
              'BIRNLEX': 'http://uri.neuinfo.org/nif/nifstd/birnlex_',
              'ILX': 'http://uri.interlex.org/base/ilx_',
              'RO': 'http://purl.obolibrary.org/obo/RO_',
              'hasRole': 'http://purl.obolibrary.org/obo/RO_0000087',
})
oq.OntCuries({
    'hasPart': oq.OntId('BFO:0000051'),
    'partOf': oq.OntId('BFO:0000050'),
})
OntId = oq.OntId


class ServiceBase:
    def setUp(self):
        _query = oq.OntQuery(self.remote)
        class OntTerm(oq.OntTerm):
            query = _query

        self.OntTerm = OntTerm
        self.OntTerm.bindQueryResult()

    def test_ontid(self):
        t = self.OntTerm(OntId('UBERON:0000955'))
        assert t.label, repr(t)

    def test_curie(self):
        t = self.OntTerm(curie='UBERON:0000955')
        assert t.iri, repr(t)

    def test_iri(self):
        t = self.OntTerm(iri='http://purl.obolibrary.org/obo/UBERON_0000955')
        assert t.curie, repr(t)

    def test_uriref(self):
        t = self.OntTerm(iri=rdflib.URIRef('http://purl.obolibrary.org/obo/UBERON_0000955'))
        assert t.curie, repr(t)

    def test_label(self):
        try:
            t = self.OntTerm(label='diffuse')
            raise AssertionError(f'should fail {t!r}')
        except oq.exceptions.OntQueryError as e:
            pass

    def test_cache(self):
        t1 = self.OntTerm('BIRNLEX:796')
        t2 = self.OntTerm('BIRNLEX:796')
        assert t1.label and t2.label, f'no lable!? {t1.__dict__} {t2.__dict__}'

    def test_curie_consistency(self):
        """ additional check to make sure that all curies are normalized on the way in """
        t = self.OntTerm('RO:0000087')


class _TestIlx(ServiceBase):
    remote = oq.plugin.get('InterLex')(host='uri.interlex.org')

    def test_problem(self):
        curie = 'ILX:0101431'
        t = self.OntTerm(curie)
        # FIXME UBERON:0000955 is lost in predicates
        assert t.curie == curie, t

    def test_no_label(self):
        t = self.OntTerm('NLX:60355')
        try:
            ser = t._graph.serialize(format='nifttl').decode()
        except rdflib.plugin.PluginException:  # if pyontutils is absent
            ser = t._graph.serialize(format='turtle').decode()

        assert t.label, ser

    def test_query_ot(self):
        """ This was an issue with incorrectly setting curie and iri in InterLexRemote.query """
        qr = next(self.OntTerm.query(label='deep'))
        #assert False, qr
        qr.OntTerm
        #wat = self.OntTerm(label='deep')  # would also trigger the issue (and then fail)

    def test_z_bad_curie(self):
        qr = next(self.OntTerm.query.services[0].query(curie='BIRNLEX:796'))


if 'CI' not in os.environ:  # production doesn't have all the required features yet
    class TestIlx(_TestIlx, unittest.TestCase):
        remote = oq.plugin.get('InterLex')(host='localhost', port='8505')


class TestSciGraph(ServiceBase, unittest.TestCase):
    remote = oq.plugin.get('SciGraph')(api_key=os.environ.get('SCICRUNCH_API_KEY', None))

    def test_inverse(self):
        t = self.OntTerm('UBERON:0000955')
        t('hasPart:')
        t('partOf:')

    def test_depth(self):
        t = self.OntTerm('UBERON:0000955')
        t('hasPart:', depth=2)


class TestRdflib(ServiceBase, unittest.TestCase):
    g = rdflib.Graph()
    triples = (('UBERON:0000955', 'rdf:type', 'owl:Class'),
               ('UBERON:0000955', 'rdfs:label', 'brain'),
               ('BIRNLEX:796', 'rdf:type', 'owl:Class'),
               ('BIRNLEX:796', 'rdfs:label', 'Brain'),
              )
    for proto_t in triples:
        g.add(rdflib.URIRef(OntId(e)) if ':' in e else rdflib.Literal(e) for e in proto_t)

    remote = oq.plugin.get('rdflib')(g)
