import unittest
from ontquery import *

class TestAll(unittest.TestCase):
    def test_query(self):
        query = OntQuery(localonts, remoteonts1, remoteonts2)  # provide by default maybe as ontquery?
        query('brain')
        query(term='brain')
        query(prefix='UBERON', id='0000955')  # it is easy to build an uberon(id='0000955') query class out of this
        query(search='thalamus')  # will probably fail with many results to choose from
        query(prefix='MBA', abbr='TH')

        uberon = OntQuery(*query, prefix='UBERON')
        uberon('brain')  # -> OntTerm('UBERON:0000955', label='brain')

        species = OntQuery(*query, category='species')
        species('mouse')  # -> OntTerm('NCBITaxon:10090', label='mouse')

    def test_term(self):
        brain = OntTerm('UBERON:0000955')
        brain = OntTerm(curie='UBERON:0000955')
        OntTerm('UBERON:0000955', label='brain')
        OntTerm('UBERON:0000955', label='not actually the brain')
        OntTerm('UBERON:0000955', label='not actually the brain', unvalidated=True)

    def test_id(self):
        OntID('UBERON:0000955')
        OntID('http://purl.obolibrary.org/obo/UBERON_0000955')
        OntID(prefix='UBERON', suffix='0000955')
