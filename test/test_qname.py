import unittest
from test import common

try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
except ModuleNotFoundError:
    from ontquery.plugins.namespaces import CURIE_MAP

import ontquery as oq


class TestOntCuries(unittest.TestCase):
    def setUp(self):
        self.OntCuries = oq.OntCuries.new()
        self.OntCuries(CURIE_MAP)

    def test_identifier_prefixes_from_curie(self):
        hit = False
        for prefix in self.OntCuries:
            curie = prefix + ':lol'
            ap = self.OntCuries.identifier_prefixes(curie)
            if ap == ['obo', 'IAO', 'isAbout']:
                hit = True

        assert hit

    def test_identifier_prefixes_from_iri(self):
        hit = False
        for iri in self.OntCuries.values():
            ap = self.OntCuries.identifier_prefixes(iri)
            if ap == ['obo', 'IAO', 'isAbout']:
                hit = True

        assert hit

    def test_identifier_prefixes_from_prefix(self):
        hit = False
        for prefix in self.OntCuries:
            ap = self.OntCuries.identifier_prefixes(prefix)
            if ap == ['obo', 'IAO', 'isAbout']:
                hit = True

        assert hit


class TestQname(unittest.TestCase):
    suffixes = common.suffixes
    def setUp(self):
        oq.OntCuries(CURIE_MAP)

    def test_exact(self):
        suffix = ''
        failed = []
        for prefix, iri in CURIE_MAP.items():
            e, g, o = self.helper(iri, prefix, suffix)
            if not (e == g == o):
                failed.append((e, g, o))

        if failed:
            raise AssertionError(str(failed))

    def test_more(self):
        failed = []
        for prefix, namespace in CURIE_MAP.items():
            for suffix in self.suffixes:
                iri = namespace + suffix
                e, g, o = self.helper(iri, prefix, suffix)
                if not (e == g == o):
                    failed.append((e, g, o))

        if failed:
            raise AssertionError(str(failed))

    def test_missing_prefix(self):
        failed = []
        for prefix, namespace in {'lol':'http://lol.com/',
                                  'hrm':'http://hrm.com/lol_',}.items():
            for suffix in self.suffixes:
                iri = namespace + suffix
                e, g, o = self.helper(iri, prefix, suffix)
                e = iri
                if not (e == g == o):
                    failed.append((e, g, o))

        if failed:
            raise AssertionError(str(failed))

    @staticmethod
    def helper(iri, prefix, suffix):
        expect = prefix + ':' + suffix
        got = oq.OntCuries.qname(iri)
        old = oq.OntCuries._qname_old(iri)
        return expect, got, old
