import unittest
from test import common

try:
    from pyontutils.namespaces import PREFIXES as CURIE_MAP
except ModuleNotFoundError:
    from ontquery.plugins.namespaces import CURIE_MAP

import ontquery as oq


class TestOntId(unittest.TestCase):
    suffixes = common.suffixes
    def setUp(self):
        oq.OntCuries(CURIE_MAP)

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

    @staticmethod
    def helper(iri, prefix, suffix):
        expect = prefix + ':' + suffix
        got = oq.OntId(curie=expect, iri=iri)
        return expect, got
