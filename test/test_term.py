import copy
import unittest
from test import common

import ontquery as oq


class TestOntId(unittest.TestCase):
    suffixes = common.suffixes
    class_to_test = oq.OntId
    kwargs_to_test = dict(curie_or_iri='TEMP:test',),

    def setUp(self):
        self.terms_to_test = tuple(self.class_to_test(**kwargs)
                                   for kwargs in self.kwargs_to_test)

    def test_multiple_colons(self):
        failed = []
        evils = (
            ('TEMP', oq.OntCuries['TEMP']),
        )
        for prefix, namespace in evils:
            for suffix in self.suffixes:
                iri = namespace + suffix
                e, g = self.helper(iri, prefix, suffix)
                e = iri
                if not (e == g):
                    failed.append((e, g))

        if failed:
            raise AssertionError(str(failed))

    @classmethod
    def helper(cls, iri, prefix, suffix):
        expect = prefix + ':' + suffix
        got = cls.class_to_test(curie=expect, iri=iri)
        return expect, got

    def test_copy(self):
        for oid in self.terms_to_test:
            noid = copy.copy(oid)
            assert oid == oid

    def test_deepcopy(self):
        for oid in self.terms_to_test:
            noid = copy.deepcopy(oid)
            assert oid == oid


class TestOntTerm(TestOntId):
    class_to_test = oq.OntTerm
    kwargs_to_test = dict(curie_or_iri='TEMP:test',), dict(curie_or_iri='TEMP:test', label='test'),
    test_copy = TestOntId.test_copy
    test_deepcopy = TestOntId.test_deepcopy

    def setUp(self):
        remote = oq.plugin.get('rdflib')(common.test_graph)
        self.class_to_test.query_init(remote)
        super().setUp()

    def test_copy_preds(self):
        ot = self.class_to_test('UBERON:0000955')
        ot(None)
        newot = copy.deepcopy(ot)
        assert ot.predicates and newot.predicates
        assert newot.predicates == ot.predicates
