import os
import unittest
import pytest
import rdflib
import ontquery as oq
from .common import skipif_no_net, CURIE_MAP


class OntTerm(oq.OntTerm):
    """ Test subclassing """

class SetupHelper:
    def setUp(self):
        #self.query = oq.OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as oq?
        #bs = oq.BasicService()  # TODO
        #self.query = oq.OntQuery(bs, upstream=OntTerm)
        #oq.QueryResult._OntTerm = OntTerm
        SCR = oq.plugin.get('SciCrunch')()
        services = SCR,
        # this was an ok idea, but better to also have known good local prefixes
        # probably need to clean up an clarify the bad old
        #services[0].setup()  # explicit call to setup so we can populate OntCuries
        #oq.OntCuries(services[0].curies)
        oq.OntCuries(CURIE_MAP)

        self.query = oq.OntQueryCli(*services, instrumented=OntTerm)
        oq.OntTerm.query_init(*services)
        #self.APIquery = OntQuery(SciGraphRemote(api_key=get_api_key()))


@skipif_no_net
class TestPredicates(SetupHelper, unittest.TestCase):
    def test_predicates_inverse(self):
        t = OntTerm('UBERON:0000955')
        o = t('hasPart:')
        assert o, 'should have had a result ...'

    def test_predicates_inverse_cli(self):
        t = self.query(iri='UBERON:0000955', predicates=('hasPart:',))[0]
        assert 'hasPart:' in t.predicates, 'should have had results'
        assert t.predicates['hasPart:'], 'should have had values if key'

    def test_predicates_sco_cli(self):
        t = self.query(iri='UBERON:0000955', predicates=('subClassOf',))[0]
        assert 'subClassOf' in t.predicates, 'should have had results'
        assert t.predicates['subClassOf'], 'should have had values if key'

    def test_predicates_rdfssco_cli(self):
        t = self.query(iri='UBERON:0000955', predicates=('rdfs:subClassOf',))[0]
        assert 'rdfs:subClassOf' in t.predicates, 'should have had results'
        assert t.predicates['rdfs:subClassOf'], 'should have had values if key'

    def test_predicates(self):
        #self.query.raw = True
        pqrl = self.query(iri='UBERON:0000955', predicates=('hasPart:',), raw=True)
        pqr = pqrl[0]
        #self.query.raw = False
        pt = pqr.asTerm()
        preds = OntTerm('UBERON:0000955')('partOf:', 'hasPart:', 'rdfs:subClassOf', 'owl:equivalentClass')
        #breakpoint()
        preds1 = pt('partOf:', 'hasPart:', 'rdfs:subClassOf', 'owl:equivalentClass')
        preds2 = OntTerm('UBERON:0000955')(rdflib.RDFS.subClassOf)
        t = OntTerm('UBERON:0000955')
        preds3 = t(rdflib.RDFS.subClassOf)
        preds4 = t('rdfs:subClassOf')
        t2 = OntTerm('UBERON:0000955', predicates=(rdflib.RDFS.subClassOf,))
        preds5 = t2.predicates

        print(preds)
        print(t.source)
        print(preds2)
        print(preds3)
        print(preds4)
        print(preds5)
        test_preds = [pqr.predicates,
                      preds,
                      preds1,
                      preds2,
                      preds3,
                      preds4]
        bads = [(i - 1, p) for i, p in enumerate(test_preds) if not p]
        assert not bads, bads

        assert isinstance(pqr.predicates, dict)
        assert isinstance(preds, dict)
        assert isinstance(preds1, dict)
        assert isinstance(preds2, tuple)
        assert isinstance(preds3, tuple)
        assert isinstance(preds4, tuple)
        assert isinstance(preds5, dict)


class TestAll(SetupHelper, unittest.TestCase):
    @skipif_no_net
    def test_query(self):
        self.query('brain')
        self.query(term='brain')
        #self.query(prefix='UBERON', suffix='0000955')  # only for OntId
        self.query(search='thalamus')  # will probably fail with many results to choose from
        self.query(prefix='MBA', abbrev='TH')

        uberon = oq.OntQueryCli(*self.query, prefix='UBERON', instrumented=OntTerm)
        brain_result = uberon('brain')  # -> OntTerm('UBERON:0000955', label='brain')

        species = oq.OntQuery(*self.query, category='species', instrumented=OntTerm)
        mouse_result = species('mouse')  # -> OntTerm('NCBITaxon:10090', label='mouse')

        list(self.query.predicates)

    @skipif_no_net
    def test_prefix(self):
        #sgv.findByTerm('nucleus', prefix=['UBERON', 'CHEBI'])
        # search by term returns all from the first prefix first
        # which is useless
        class OntTerm(oq.OntTerm):
            pass
        prefix = 'UBERON', 'CHEBI', 'GO'
        query = OntTerm.query_init(*self.query, prefix=prefix)
        result = list(query(term='nucleus'))
        assert [term for term in result if term.prefix == 'UBERON']
        assert [term for term in result if term.prefix == 'CHEBI']
        assert [term for term in result if term.prefix == 'GO']
        assert not [term for term in result if term.suffix == 'SAO']

    @skipif_no_net
    def test_category(self):
        class OntTerm(oq.OntTerm):
            pass

        #sgv.findByTerm('nucleus', category=['subcellular entity', 'anatomical entity'])
        cat = 'anatomical entity', 'subcellular entity'
        query = OntTerm.query_init(*self.query, category=cat)
        result = list(query(term='nucleus'))
        assert [term for term in result if term.prefix == 'UBERON']
        assert [term for term in result if term.prefix == 'GO']
        assert not [term for term in result if term.suffix == 'CHEBI']

    @skipif_no_net
    def test_term(self):
        brain = OntTerm('UBERON:0000955')
        brain = OntTerm(curie='UBERON:0000955')
        OntTerm('UBERON:0000955', label='brain')
        OntTerm('NCBITaxon:2', label='Bacteria')
        #OntTerm('NCBITaxon:2', label='Bacteria <prokaryote>')  # gone in latest

    @skipif_no_net
    def test_term_label_mismatch(self):
        try:
            l = 'not actually the brain'
            t = OntTerm('UBERON:0000955', label=l)
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

    @skipif_no_net
    def test_term_label_mismatch_not_validated(self):
        try:
            OntTerm('UBERON:0000955', label='not actually the brain', validated=False)
            assert False, 'should not get here'
        except ValueError:
            assert True, 'expect to fail'

    def test_term_query(self):
        """ this functionality has been removed these should all return TypeErrors """
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
        except TypeError:
            assert True, 'fails as expected'

        try:
            OntTerm(label='dorsal plus ventral thalamus')
            assert False, 'should not get here!'
        except TypeError:
            assert True, 'fails as expected'

    @skipif_no_net
    def test_dont_return_OntTerm_from_query(self):
        """ no idea why this test is here, but apparently we had a very funny bug at some point in time """
        #t = next(OntTerm.query(term='midbrain reticular nucleus')).OntTerm
        t = next(OntTerm.query(term='serotonin', prefix='CHEBI'))
        assert t != OntTerm

    def test_id(self):
        oq.OntId('UBERON:0000955')
        oq.OntId('http://purl.obolibrary.org/obo/UBERON_0000955')
        oq.OntId(prefix='UBERON', suffix='0000955')

    def test_a_curies(self):
        oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/'
        a = oq.OntCuries['new-prefix']
        oq.OntId('new-prefix:working')

    def test_b_curie_lookup_fail(self):
        try:
            b = oq.OntCuries['not-a-prefix']
            assert False, 'should not get here'
        except KeyError:
            assert True, 'should fail'

    def test_c_curie_overwrite_fail(self):
        try:
            oq.OntCuries['new-prefix'] = 'https://my-prefixed-thing.org/fail/'
            assert False, 'should not get here'
        except KeyError:
            assert True, 'should fail'

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

    @skipif_no_net
    def test_prefix(self):
        bads = []
        for prefix in 'UBERON', 'FMA':
            gen = oq.OntTerm.query(term='brain', prefix=prefix)
            bads += [term for term in gen if term.prefix != prefix]

        assert not bads, bads

    @skipif_no_net
    def test_prefixes(self):
        prefixes = ('UBERON', 'BIRNLEX', 'FMA')
        gen = oq.OntTerm.query(term='brain', prefix=prefixes)
        bads = [term for term in gen if term.prefix not in prefixes]
        assert not bads, bads

    @skipif_no_net
    def test_exclude_prefix(self):
        gen = oq.OntTerm.query(term='brain', exclude_prefix=('FMA',))
        bads = [term for term in gen if term.prefix == 'FMA']
        assert not bads, bads
