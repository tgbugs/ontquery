import unittest
import ontquery
from pyontutils import core

class OntTerm(ontquery.OntTerm):
    """ Test subclassing """

class TestAll(unittest.TestCase):
    def setUp(self):
        ontquery.OntCuries(core.PREFIXES)
        #self.query = OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as ontquery?
        self.query = ontquery.OntQuery(ontquery.SciGraphRemote(apiEndpoint='http://localhost:9000/scigraph'),
                                       upstream=OntTerm)
        #self.APIquery = OntQuery(SciGraphRemote(api_key=get_api_key()))

    def test_query(self):

        self.query('brain')
        self.query(term='brain')
        #self.query(prefix='UBERON', suffix='0000955')  # only for OntId
        self.query(search='thalamus')  # will probably fail with many results to choose from
        self.query(prefix='MBA', abbrev='TH')

        uberon = ontquery.OntQuery(*self.query, prefix='UBERON')
        brain_result = uberon('brain')  # -> OntTerm('UBERON:0000955', label='brain')

        species = ontquery.OntQuery(*self.query, category='species')
        mouse_result = species('mouse')  # -> OntTerm('NCBITaxon:10090', label='mouse')

        list(self.query.predicates)

    def test_term(self):
        brain = OntTerm('UBERON:0000955')
        brain = OntTerm(curie='UBERON:0000955')
        OntTerm('UBERON:0000955', label='brain')
        OntTerm('UBERON:0000955', label='not actually the brain')
        OntTerm('UBERON:0000955', label='not actually the brain', unvalidated=True)

    def test_id(self):
        ontquery.OntId('UBERON:0000955')
        ontquery.OntId('http://purl.obolibrary.org/obo/UBERON_0000955')
        ontquery.OntId(prefix='UBERON', suffix='0000955')

    def test_predicates(self):
        pqr = self.query(iri='UBERON:0000955', predicates=('hasPart:',))
        pt = pqr.asTerm()
        preds = OntTerm('UBERON:0000955')('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
        preds1 = pt('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
