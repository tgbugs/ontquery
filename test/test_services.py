import os
import unittest
from uuid import uuid4
import pytest
import rdflib
import ontquery as oq
from .common import test_graph, skipif_no_net, log
from .test_interlex_client import skipif_no_api_key

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
        class OntTerm(oq.OntTerm): pass
        OntTerm.query_init(self.remote)
        self.OntTerm = OntTerm

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
        """ functionality was removed, should TypeError now """
        try:
            t = self.OntTerm(label='diffuse')
            raise AssertionError(f'should fail {t!r}')
        except TypeError:
            pass

    def test_definition(self):
        t1 = self.OntTerm('BIRNLEX:796')
        assert not t1.validated or t1.definition is not None

    def test_synonyms(self):
        t1 = self.OntTerm('BIRNLEX:796')
        if not t1.validated or not t1.synonyms:  # No syns in SciGraph
            t1 = self.OntTerm('BIRNLEX:798')

        assert not t1.validated or len(t1.synonyms)

    def test_cache(self):
        t1 = self.OntTerm('BIRNLEX:796')
        t2 = self.OntTerm('BIRNLEX:796')
        assert t1.label and t2.label, f'no lable!? {t1.__dict__} {t2.__dict__}'

    def test_curie_consistency(self):
        """ additional check to make sure that all curies are normalized on the way in """
        t = self.OntTerm('RO:0000087')

    def test_curie_404(self):
        t = self.OntTerm('TEMP:curie/does/not/exist')


class _TestIlx(ServiceBase):
    remote = oq.plugin.get('InterLex')()
    skipif_not_dev = pytest.mark.skipif(not remote.port, reason='only implemented on dev')

    @skipif_not_dev
    def test_cache(self):
        super().test_cache()

    @skipif_not_dev
    def test_ontid(self):
        super().test_cache()

    def test_problem(self):
        curie = 'ILX:0101431'
        t = self.OntTerm(curie)
        # FIXME UBERON:0000955 is lost in predicates
        assert t.curie == curie, t

    @skipif_not_dev
    def test_wrong_label(self):
        t = self.OntTerm('ILX:0110092')
        l = t.label
        assert 'II' in l

    @skipif_not_dev
    def test_no_label(self):
        t = self.OntTerm('NLX:60355')
        try:
            ser = t._graph.serialize(format='nifttl')
        except rdflib.plugin.PluginException:  # if pyontutils is absent
            ser = t._graph.serialize(format='turtle')

        assert t.label, ser

    @skipif_not_dev
    def test_query_ot(self):
        """ This was an issue with incorrectly setting curie and iri in InterLexRemote.query """
        try:
            term = next(self.OntTerm.query(label='deep'))
            assert term, 'oops?'
        except StopIteration:
            pytest.skip('term not in db')

    @skipif_not_dev
    def test_z_bad_curie(self):
        qr = next(self.OntTerm.query.services[0].query(curie='BIRNLEX:796'))

    @skipif_no_api_key
    def test_zz_add_entity(self):  # needs zz so that it runs after setup()
        qr = self.remote.add_entity(
            type='term',
            label=f'test term 9000 {uuid4()}',
            subThingOf='http://uri.interlex.org/base/tmp_0109677',
            definition='hhohohoho')
        print(qr)
        # NOTE the values in the response are a mishmash of garbage because
        # the tmp_ ids were never properly abstracted

    @skipif_no_api_key
    def test_add_pde(self):
        qr = self.remote.add_pde(f'test pde {uuid4()}')
        print(qr)

    @skipif_no_api_key
    @pytest.mark.skip(reason='interlex api is not ready')
    def test_multi_sco(self):
        # XXX this requires that interlex server alt be running with
        # interlex.dump.MysqlExport._term_triples(include_supers=True)
        # which has been prototyped, but the api is not stable so we
        # skip this for now
        term = self.OntTerm('ILX:0793561')
        sco1 = term('rdfs:subClassOf', depth=1)
        scon = term('rdfs:subClassOf', depth=99)
        assert len(sco1) == 1
        assert len(sco1) < len(scon)  # that we get parents
        assert len(set(scon)) == len(scon)  # that we get them only once


if 'CI' not in os.environ:  # production uri resolver doesn't have all the required features yet
    beta = 'https://test3.scicrunch.org/api/1/'
    @skipif_no_net
    class TestIlx(_TestIlx, unittest.TestCase):
        remote = oq.plugin.get('InterLex')(apiEndpoint=beta)
        def setUp(self):
            super().setUp()
            self.OntTerm.query.setup()


@skipif_no_net
class TestSciGraph(ServiceBase, unittest.TestCase):
    remote = oq.plugin.get('SciGraph')()

    def test_inverse(self):
        t = self.OntTerm('UBERON:0000955')
        t('hasPart:')
        t('partOf:')

    def test_depth(self):
        t = self.OntTerm('UBERON:0000955')
        t('hasPart:', depth=2)

    def test_query_bad_prefix(self):
        try:
            term = next(self.OntTerm.query(label='brain', prefix='notaprefix'))
            raise AssertionError(f'should fail {t!r}')
        except ValueError as e:
            pass


class TestRdflib(ServiceBase, unittest.TestCase):
    remote = oq.plugin.get('rdflib')(test_graph)

    def test_depth(self):
        t = self.OntTerm('UBERON:0000955')
        o1 = t('rdfs:subClassOf', depth=1)
        o2 = t('rdfs:subClassOf', depth=2)
        on = t('rdfs:subClassOf', depth=99)
        assert len(o1) == 1
        assert len(o2) == 2
        assert len(on) == len(t.predicates['rdfs:subClassOf'])

    def test_cycle(self):
        t = self.OntTerm('TEMP:cycle-1')
        oops = t('rdfs:subClassOf', depth=99)
        assert len(oops) == 3, 'oh no'


@skipif_no_net
class TestGitHub(ServiceBase, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.remote = oq.plugin.get('GitHub')(
            'SciCrunch', 'NIF-Ontology',
            'ttl/bridge/uberon-bridge.ttl',
            'ttl/NIF-GrossAnatomy.ttl', branch='dev')

    def test_ontid(self):
        t = self.OntTerm(OntId('BIRNLEX:796'))
        assert t.label, repr(t)
