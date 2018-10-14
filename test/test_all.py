import os
import unittest
import rdflib
from pyontutils import scigraph_client  # this must be imported first to preserve the original path

# orig_basepath = scigraph_client.BASEPATH
# FIXME nosetests is somehow importing something at a point that I cannot detect
# that overwrites this with the devconfig options, despite it working correctly with python -m unittest
orig_basepath = 'https://scicrunch.org/api/1/scigraph'

from pyontutils import namespaces
from pyontutils import scigraph
from pyontutils import config
from pyontutils import core
import ontquery as oq

if 'SCICRUNCH_API_KEY' in os.environ:
    scigraph.scigraph_client.BASEPATH = orig_basepath
else:
    scigraph.scigraph_client.BASEPATH = 'http://localhost:9000/scigraph'

class OntTerm(oq.OntTerm):
    """ Test subclassing """


OntTerm.bindQueryResult()


class TestAll(unittest.TestCase):
    def setUp(self):
        oq.OntCuries(namespaces.PREFIXES)
        #self.query = oq.OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as oq?
        #bs = oq.BasicService()  # TODO
        #self.query = oq.OntQuery(bs, upstream=OntTerm)
        #oq.QueryResult._OntTerm = OntTerm
        if 'SCICRUNCH_API_KEY' in os.environ:
            services = oq.plugin.get('SciCrunch')(api_key=config.get_api_key()),
        else: services = oq.plugin.get('SciCrunch')(apiEndpoint='http://localhost:9000/scigraph'),

        self.query = oq.OntQueryCli(*services)
        oq.OntTerm.query = oq.OntQuery(*services)
        #self.APIquery = OntQuery(SciGraphRemote(api_key=get_api_key()))

    def test_query(self):
        self.query('brain')
        self.query(term='brain')
        #self.query(prefix='UBERON', suffix='0000955')  # only for OntId
        self.query(search='thalamus')  # will probably fail with many results to choose from
        self.query(prefix='MBA', abbrev='TH')

        uberon = oq.OntQueryCli(*self.query, prefix='UBERON')
        brain_result = uberon('brain')  # -> OntTerm('UBERON:0000955', label='brain')

        species = oq.OntQuery(*self.query, category='species')
        mouse_result = species('mouse')  # -> OntTerm('NCBITaxon:10090', label='mouse')

        list(self.query.predicates)

    def test_term(self):
        brain = OntTerm('UBERON:0000955')
        brain = OntTerm(curie='UBERON:0000955')
        OntTerm('UBERON:0000955', label='brain')
        OntTerm('NCBITaxon:2', label='Bacteria')
        #OntTerm('NCBITaxon:2', label='Bacteria <prokaryote>')  # gone in latest
        try:
            l = 'not actually the brain'
            t = OntTerm('UBERON:0000955', label=l)
            from IPython import embed
            embed()
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

        try:
            OntTerm('UBERON:0000955', label='not actually the brain', validated=False)
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

    def test_term_query(self):
        _query = oq.OntTerm.query
        oq.OntTerm.query = self.query
        try:
            OntTerm(label='brain')
            assert False, 'should not get here!'
        except TypeError:
            assert True, 'fails as expected'

        oq.OntTerm.query = _query

        try:
            OntTerm(label='brain', prefix='UBERON')
            assert False, 'should not get here!'
        except oq.exceptions.NoExplicitIdError:
            assert True, 'fails as expected'

        try:
            OntTerm(label='dorsal plus ventral thalamus')
            assert False, 'should not get here!'
        except oq.exceptions.NoExplicitIdError:
            assert True, 'fails as expected'

        #t = next(OntTerm.query(term='midbrain reticular nucleus')).OntTerm
        t = next(OntTerm.query(term='serotonin', prefix='CHEBI')).OntTerm
        assert t != OntTerm

    def test_id(self):
        oq.OntId('UBERON:0000955')
        oq.OntId('http://purl.obolibrary.org/obo/UBERON_0000955')
        oq.OntId(prefix='UBERON', suffix='0000955')

    def test_predicates(self):
        self.query.raw = True
        pqr = self.query(iri='UBERON:0000955', predicates=('hasPart:',))
        self.query.raw = False
        pt = pqr.OntTerm
        preds = OntTerm('UBERON:0000955')('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
        preds1 = pt('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
        preds2 = OntTerm('UBERON:0000955')(core.rdfs.subClassOf)

        assert pqr.predicates
        assert preds
        assert preds1
        assert preds2

        assert isinstance(pqr.predicates, dict)
        assert isinstance(preds, dict)
        assert isinstance(preds1, dict)
        assert isinstance(preds2, dict)

    def test_curies(self):
        oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        a = oq.OntCuries['new-prefix']
        try:
            b = oq.OntCuries['not-a-prefix']
            assert False, 'should not get here'
        except KeyError:
            assert True, 'should fail'

        try:
            oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/fail/'
            assert False, 'should not get here'
        except KeyError:
            assert True, 'should fail'

        oq.OntId('new-prefix:working')

    def test_ontid_curie_uriref(self):
        c = oq.OntId(rdflib.URIRef(oq.OntId('RO:0000087')))
        cl = oq.OntId('RO:0000087')
        assert c.curie == cl.curie, f'{c!r} != {cl!r}'

    def test_ontid_iri(self):
        oq.OntId(iri='http://uri.neuinfo.org/nifa/nifstd/birnleex_796')

    def test_ontid_curie(self):
        oq.OntId(curie='BIRNLEX:796')

    def test_ontid_curie_as_iri(self):
        try:
            oq.OntId(iri='BIRNLEX:796')
            raise AssertionError('should have failed with ValueError')
        except ValueError:
            pass
