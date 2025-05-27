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
                if not (e == str(g)):
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

    def test_type_recursion(self):
        bads = []
        for term in self.terms_to_test:
            # note we aren't testing inst vs uninst right now
            nt = self.class_to_test(term, iri=term, curie=term)
            if term != nt:
                bads.append((term, nt))

        assert not bads, 'oh no'


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


class TestInterveningInstrumented(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class OntTerm1(oq.OntTerm): pass
        class OntTerm2(OntTerm1): pass
        cls.OntTerm1 = OntTerm1
        cls.OntTerm2 = OntTerm2

        class OntTerm3(OntTerm1): pass
        cls.OntTerm3 = OntTerm3

    def test_0(self):
        key = oq.utils.SubClassCompare
        uninst_class_c = self.OntTerm3._uninstrumented_class()
        ot3 = key(self.OntTerm3)
        ucc = key(uninst_class_c)
        assert ucc < ot3 and ot3 > ucc

    def test_1(self):
        uninst_class_a = self.OntTerm2._uninstrumented_class()
        inst_class_a = uninst_class_a._instrumented_class()
        uninst_class_b = self.OntTerm2._uninstrumented_class()
        inst_class_b = uninst_class_b._instrumented_class()

        assert uninst_class_a is not oq.OntId, 'new uninstrumented class was not created'
        assert uninst_class_a is uninst_class_b, 'uninstrumented classes differ between calls'

        wat = [oq.utils.SubClassCompare(_) for _ in oq.utils.subclasses(oq.OntId)]
        assert sorted(wat) != sorted(wat, reverse=True), f'seriously? what is going on here {wat}'

        assert inst_class_a is not oq.OntId._instrumented_class(), 'new instrumented class is the base instrumented class'
        assert inst_class_a is self.OntTerm2, 'instrumented class from new uninstrumented class is not the originating instrumented class'
        assert inst_class_a is inst_class_b, 'instrumented classes differ between calls'

    def test_2(self):
        self.OntTerm1.query
        hrm = self.OntTerm1._uninstrumented_class()._instrumented_class()
        hrm.query
