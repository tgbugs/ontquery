import os
import unittest
import rdflib
try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
    from pyontutils import scigraph
    orig_basepath = 'https://scicrunch.org/api/1/sparc-scigraph'  # FIXME hardcoding
    if 'SCICRUNCH_API_KEY' in os.environ:
        scigraph.scigraph_client.BASEPATH = orig_basepath
    else:
        scigraph.scigraph_client.BASEPATH = 'http://localhost:9000/scigraph'
except ModuleNotFoundError:
    from ontquery.plugins.namespaces import CURIE_MAP
    from ontquery.plugins import scigraph_client as scigraph

import ontquery as oq
oq.utils.log.setLevel('DEBUG')


class OntTerm(oq.OntTerm):
    """ Test subclassing """


class TestAll(unittest.TestCase):
    def setUp(self):
        #self.query = oq.OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as oq?
        #bs = oq.BasicService()  # TODO
        #self.query = oq.OntQuery(bs, upstream=OntTerm)
        #oq.QueryResult._OntTerm = OntTerm
        if 'SCICRUNCH_API_KEY' in os.environ:
            SCR = oq.plugin.get('SciCrunch')()
            SCR.api_key = os.environ['SCICRUNCH_API_KEY']
        else:
            SCR = oq.plugin.get('SciCrunch')(apiEndpoint='http://localhost:9000/scigraph')

        services = SCR,
        # this was an ok idea, but better to also have known good local prefixes
        # probably need to clean up an clarify the bad old
        #services[0].setup()  # explicit call to setup so we can populate OntCuries
        #oq.OntCuries(services[0].curies)
        oq.OntCuries(CURIE_MAP)

        self.query = oq.OntQueryCli(*services, instrumented=OntTerm)
        oq.OntTerm.query_init(*services)
        #self.APIquery = OntQuery(SciGraphRemote(api_key=get_api_key()))

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

    def test_prefix(self):
        #sgv.findByTerm('nucleus', prefix=['UBERON', 'CHEBI'])
        # search by term returns all from the first prefix first
        # which is useless
        class OntTerm(oq.OntTerm):
            pass
        prefix = 'UBERON', 'CHEBI', 'GO'
        query = OntTerm.query_init(*self.query, prefix=prefix)
        result = list(query(term='nucleus'))
        assert [qr for qr in result if qr.OntTerm.prefix == 'UBERON']
        assert [qr for qr in result if qr.OntTerm.prefix == 'CHEBI']
        assert [qr for qr in result if qr.OntTerm.prefix == 'GO']
        assert not [qr for qr in result if qr.OntTerm.suffix == 'SAO']

    def test_category(self):
        class OntTerm(oq.OntTerm):
            pass

        #sgv.findByTerm('nucleus', category=['subcellular entity', 'anatomical entity'])
        cat = 'anatomical entity', 'subcellular entity'
        query = OntTerm.query_init(*self.query, category=cat)
        result = list(query(term='nucleus'))
        assert [qr for qr in result if qr.OntTerm.prefix == 'UBERON']
        assert [qr for qr in result if qr.OntTerm.prefix == 'GO']
        assert not [qr for qr in result if qr.OntTerm.suffix == 'CHEBI']

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

    def test_prefix(self):
        bads = []
        for prefix in 'UBERON', 'FMA':
            gen = oq.OntTerm.query(term='brain', prefix=prefix)
            bads += [qr for qr in gen if qr.OntTerm.prefix != prefix]

        assert not bads, bads

    def test_prefixs(self):
        prefixes = ('UBERON', 'BIRNLEX', 'FMA')
        gen = oq.OntTerm.query(term='brain', prefix=prefixes)
        bads = [qr for qr in gen if qr.OntTerm.prefix not in prefixes]
        assert not bads, bads

    def test_exclude_prefix(self):
        gen = oq.OntTerm.query(term='brain', exclude_prefix=('FMA',))
        bads = [qr for qr in gen if qr.OntTerm.prefix == 'FMA']
        assert not bads, bads
