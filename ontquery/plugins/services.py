def main():
    import os
    from IPython import embed
    from pyontutils.namespaces import PREFIXES as uPREFIXES
    from pyontutils.config import get_api_key
    from ontquery.utils import QueryResult
    curies = OntCuries(uPREFIXES)
    #print(curies)
    i = InterLexRemote()
    services = SciGraphRemote(api_key=get_api_key()), i
    OntTerm.query = OntQuery(*services)
    #out = list(i.query('NLX:143939'))
    #sout = list(OntTerm.query(curie='NLX:143939'))

    q = list(i.query(curie='ILX:0300352'))
    qq = list(OntTerm.query(curie='ILX:0300352'))
    print(q, qq)
    #embed()
    return
    query = OntQueryCli(query=OntTerm.query)
    query.raw = True  # for the demo here return raw query results
    QueryResult._OntTerm = OntTerm

    # direct use of query instead of via OntTerm, users should never have to do this
    qr = query(label='brain', prefix='UBERON')
    t = qr.OntTerm  # creation of a term using QueryResult.OntTerm
    t1 = OntTerm(**qr)  # creation of a term by passing a QueryResult instance to OntTerm as a dictionary

    # predicates query
    pqr = query(iri='UBERON:0000955', predicates=('hasPart:',))
    pt = pqr.OntTerm
    preds = OntTerm('UBERON:0000955')('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')
    preds1 = t('hasPart:', 'partOf:', 'rdfs:subClassOf', 'owl:equivalentClass')

    # query enabled OntTerm, throws a ValueError if there is no identifier
    try:
        t2 = OntTerm(term='brain', prefix='UBERON')
    except ValueError as e:
        print(red.format(e))
    try:
        t2 = OntTerm(label='brain', prefix='UBERON')
    except ValueError as e:
        print(red.format(e))
    t2 = OntTerm('UBERON:0000955', label='brain')

    print(repr(t))
    #*(print(repr(_)) for _ in (t, t1, t2)),

    def test(func):
        #expected fails
        #func(prefix='definition'),
        #func(suffix=''),
        asdf = (
            func('definition:'),
            func(prefix='definition', suffix=''),
            func(curie='definition:'),
            func('http://purl.obolibrary.org/obo/IAO_0000115'),
            func(iri='http://purl.obolibrary.org/obo/IAO_0000115'),
            )
        [print(repr(_)) for _ in asdf]
        return asdf

    test(OntId)
    asdf = test(OntTerm)


if __name__ == '__main__':
    pass
