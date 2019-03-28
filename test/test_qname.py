import unittest

try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
except ModuleNotFoundError:
    from ontquery.plugins.namespaces import CURIE_MAP

import ontquery as oq


class TestQname(unittest.TestCase):
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

    suffixes = (
        '',
        'hello',
        'world',
        '1234567',
        '1232/123123/asdfasdf',
        'lol_this#is/even-worse/_/123'
    )

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
