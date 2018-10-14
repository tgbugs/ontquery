from ontquery import OntCuries, OntId
from ontquery.utils import cullNone
from ontquery.query import QueryResult
from ontquery.services import OntService
try:
    from pyontutils import scigraph
except ModuleNotFoundError:
    from . import scigraph_client as scigraph

try:
    import requests
except ModuleNotFoundError as requests_missing:
    pass  # we warn later if this fails

try:
    import rdflib
except ModuleNotFoundError as rdflib_missing:
    pass  # we warn later if this fails

class SciGraphRemote(OntService):  # incomplete and not configureable yet
    cache = True
    verbose = False
    known_inverses = ('', ''),
    def __init__(self, api_key=None, apiEndpoint=None, OntId=OntId):  # apiEndpoint=None -> default from pyontutils.devconfig
        try:
            requests
        except NameError:
            raise ModuleNotFoundError('You need to install requests to use this service') from requests_missing
        self.basePath = apiEndpoint
        self.api_key = api_key
        self.OntId = OntId
        super().__init__()

    @property
    def inverses(self):
        inverses = {self.OntId(k):self.OntId(v)
                    for _k, _v in self.known_inverses
                    for k, v in ((_k, _v), (_v, _k))
                    if _k and _v}

        return inverses

    def add(self, iri):  # TODO implement with setter/appender?
        raise TypeError('Cannot add ontology to remote service.')

    @property
    def predicates(self):
        yield from self._predicates

    def setup(self):
        # TODO make it possible to set these properties dynamically
        # one way is just to do scigraph = SciGraphRemote \\ OntQuery(scigraph)
        self.sgv = scigraph.Vocabulary(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.sgg = scigraph.Graph(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.sgc = scigraph.Cypher(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.curies = self.sgc.getCuries()  # TODO can be used to provide curies...
        self.prefixes = sorted(self.curies)
        self.search_prefixes = [p for p in self.prefixes if p != 'SCR']
        self.categories = self.sgv.getCategories()
        self._predicates = sorted(set(self.sgg.getRelationships()))
        #self._onts = sorted(o['n']['iri'] for o in self.sgc.execute('MATCH (n:Ontology) RETURN n', 1000, 'application/json'))  # only on newer versions, update when we switch production over
        self._onts = sorted(o['iri'] for o in self.sgc.execute('MATCH (n:Ontology) RETURN n', 1000, 'text/plain'))
        super().setup()

    def _graphQuery(self, subject, predicate, depth=1, direction='OUTGOING', inverse=False):
        # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
        # TODO how to handle depth? this is not an obvious or friendly way to do this
        if ':' in predicate and predicate.prefix in ('owl', 'rdfs'):
            p = predicate.suffix
        else:
            p = predicate
        d_nodes_edges = self.sgg.getNeighbors(subject, relationshipType=p,
                                              depth=depth, direction=direction)  # TODO
        if d_nodes_edges:
            edges = d_nodes_edges['edges']
            #print('aaaaaaaaaaaaaaaaa', len(edges))   # TODO len(set(???))
        else:
            if inverse:  # it is probably a bad idea to try to be clever here
                predicate = self.inverses[predicate]
            print(f'{subject.curie} has no edges with predicate {predicate.curie} ')
            return

        s, o = 'sub', 'obj'
        if inverse:
            s, o = o, s
        if depth > 1:
            #subjects = set(subject.curie)
            seen = {subject.curie}
            for i, e in enumerate(self.sgg.ordered(subject.curie, edges, inverse=inverse)):
                #print('record number:', i)  # FIXME
                # FIXME need to actually get the transitive closure, this doesn't actually work
                #if e[s] in subjects:
                    #subjects.add(object.curie)
                object = e[o]
                if object not in seen:
                    # to make OntTerm(object) work we need to be able to use the 'meta' section...
                    # and would have to fetch the object directly anyway since OntTerm requires
                    # direct atestation ... which suggests that we probably need/want a bulk constructor
                    seen.add(object)
                    yield self.OntId(object) # FIXME TODO this is _very_ inefficient for multiple lookups...
        else:
            objects = (self.OntId(e[o]) for e in edges if e[s] == subject.curie)
            yield from objects

    def query(self, iri=None, curie=None,
              label=None, term=None, search=None, abbrev=None,  # FIXME abbrev -> any?
              prefix=None, category=None,
              predicates=tuple(), depth=1,
              direction='OUTGOING', limit=10):
        # use explicit keyword arguments to dispatch on type
        if prefix is not None and prefix not in self.curies:
            raise ValueError(f'{prefix} not in {self.__class__.__name__}.prefixes')
        if category is not None and category not in self.categories:
            raise ValueError(f'{category} not in {self.__class__.__name__}.categories')

        if (prefix is None and any((label, term, search, abbrev)) and
            self.prefixes != self.search_prefixes):
            prefix = self.search_prefixes

        qualifiers = cullNone(prefix=prefix, category=category, limit=limit)
        identifiers = cullNone(iri=iri, curie=curie)
        predicates = tuple(self.OntId(p) if ':' in p else
                           p for p in predicates)
        if identifiers:
            identifier = self.OntId(next(iter(identifiers.values())))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # this does not accept qualifiers
            if result is None:
                return

            if predicates:  # TODO incoming/outgoing, 'ALL' by depth to avoid fanout
                for predicate in predicates:
                    values = tuple(sorted(self._graphQuery(identifier, predicate,
                                                           depth=depth, direction=direction)))
                    if values:
                        result[predicate] = values

                    if predicate in self.inverses:
                        p = self.inverses[predicate]
                        inv_direction = ('OUTGOING' if
                                         direction == 'INCOMING' else
                                         ('INCOMING' if
                                          direction == 'OUTGOING'
                                          else direction))
                        inv_values = tuple(sorted(self._graphQuery(identifier, p,
                                                                   depth=depth, direction=inv_direction,
                                                                   inverse=True)))
                        if values or predicate in result:
                            rp = result[predicate]
                            fv = tuple(v for v in inv_values if v not in rp)
                            result[predicate] += fv
                        elif inv_values:
                            result[predicate] = inv_values

            results = result,
        elif term:
            results = self.sgv.findByTerm(term, searchSynonyms=True, **qualifiers)
        elif label:
            results = self.sgv.findByTerm(label, searchSynonyms=False, **qualifiers)
        elif search:
            qualifiers['limit'] = 100  # FIXME deprecated issue
            results = self.sgv.searchByTerm(search, **qualifiers)
        elif abbrev:
            results = self.sgv.findByTerm(abbrev, searchSynonyms=True,
                                          searchAbbreviations=True,
                                          searchAcronyms=True,
                                          **qualifiers)
        else:
            raise ValueError('No query prarmeters provided!')

        # TODO deprecated handling

        # TODO transform result to expected
        count = 0
        for result in results:
            if result['deprecated'] and not identifiers:
                continue
            ni = lambda i: next(iter(sorted(i))) if i else None  # FIXME multiple labels issue
            predicate_results = {predicate.curie if ':' in predicate else predicate:result[predicate]  # FIXME hack
                                 for predicate in predicates  # TODO depth=1 means go ahead and retrieve?
                                 if predicate in result}  # FIXME hasheqv on OntId
            # print(red.format('PR:'), predicate_results, result)
            qr = QueryResult(query_args={**qualifiers, **identifiers, 'predicates':predicates},
                             iri=result['iri'],
                             curie=result['curie'] if 'curie' in result else result['iri'],  # FIXME...
                             label=ni(result['labels']),
                             labels=result['labels'],
                             definition=ni(result['definitions']),
                             synonyms=result['synonyms'],
                             deprecated=result['deprecated'],
                             acronym=result['acronyms'],
                             abbrev=result['abbreviations'],
                             prefix=result['curie'].split(':')[0] if 'curie' in result else None,
                             category=ni(result['categories']),
                             predicates=predicate_results,
                             source=self)
            yield qr
            if count >= limit:  # FIXME deprecated issue
                break
            else:
                count += 1


class SciCrunchRemote(SciGraphRemote):
    known_inverses = ('partOf:', 'hasPart:'),
    defaultEndpoint = 'https://scicrunch.org/api/1/scigraph'
    def __init__(self, api_key=None, apiEndpoint=defaultEndpoint, OntId=OntId):
        if api_key is None:
            import os
            try:
                api_key = os.environ['SCICRUNCH_API_KEY']
            except KeyError:
                pass

        if api_key is None and apiEndpoint == self.defaultEndpoint:
            raise ValueError('You have not set an API key for the SciCrunch API!')

        super().__init__(api_key=api_key, apiEndpoint=apiEndpoint, OntId=OntId)

    def termRequest(self, term):
        if term.validated:
            raise TypeError('Can\'t add a term that already exists!')

        print('It seems that you have found a terms that is not in your remote! '
              'To request inclusion of this term please open the link in a browser or '
              'run the function returned by this which can be found in the list at '
              f'{term.__class__.__name__}.termRequests for this term {term!r}.')

        class TermRequest(term.__class__):
            # TODO iri, curie, prefix, label, etc.
            # test to make sure that the term is not in the ontology
            # and that it has not already been requested
            post_url = 'https://ontology.neuinfo.org/term-request'  # TODO
            def __init__(self):
                self.__done = False
                super().__init__(**term)
            def __call__(self):
                if not self.__done:
                    resp = requests.post(post_url, data=self)  # TODO
                    self.__done = True
                    # TODO handle terms already requested but not in this session
                else:
                    print('This term has already been requested')

            def url_link(self):
                return post_template + 'TODO-TODO-TODO'


class InterLexRemote(OntService):  # note to self
    known_inverses = ('', ''),

    def __init__(self, *args, host='uri.interlex.org', port='', **kwargs):
        try:
            requests
        except NameError:
            raise ModuleNotFoundError('You need to install requests to use this service') from requests_missing
        self.host = host
        self.port = port
        self._graph_cache = {}

        self.Graph = rdflib.Graph
        self.RDF = rdflib.RDF
        self.OWL = rdflib.OWL
        self.URIRef = rdflib.URIRef
        #self.curies = requests.get(f'http://{self.host}:{self.port}/base/curies').json()  # FIXME TODO
        # here we see that the original model for curies doesn't quite hold up
        # we need to accept local curies, but we also have to have them
        # probably best to let the user populate their curies from interlex
        # at the start, rather than having it be completely wild
        # FIXME can't do this at the moment because interlex itself calls this --- WHOOPS
        super().__init__(*args, **kwargs)

    @property
    def host_port(self):
        return f'{self.host}:{self.port}' if self.port else self.host

    @property
    def predicates(self):
        return {}  # TODO

    def query(self, iri=None, curie=None, label=None, term=None, predicates=None, **_):
        kwargs = cullNone(iri=iri, curie=curie, label=label, term=term, predicates=predicates)
        def get(url, headers={'Accept':'application/n-triples'}):  # FIXME extremely slow?
            with requests.Session() as s:
                s.headers.update(headers)
                resp = s.get(url, allow_redirects=False)
                while resp.is_redirect and resp.status_code < 400:  # FIXME redirect loop issue
                    # using send means that our headers don't show up in every request
                    resp = s.get(resp.next.url, allow_redirects=False)
                    if not resp.is_redirect:
                        break
            return resp

        def isAbout(g):
            ontid, *r1 = g[:self.RDF.type:self.OWL.Ontology]
            o, *r2 = g[ontid:self.URIRef('http://purl.obolibrary.org/obo/IAO_0000136')]
            if r1 or r2:
                raise ValueError(f'NonUnique value for ontology {r1} or about {r2}')
            return o

        if iri:
            oiri = OntId(iri=iri)
            icurie = oiri.curie
            if curie and icurie != curie:
                raise ValueError(f'curie and curied iri do not match {curie} {icurie}')
            else:
                curie = icurie
        elif curie:
            iri = OntId(curie).iri

        if curie:
            if curie.startswith('ILX:') and iri:
                # FIXME hack, can replace once the new resolver is up
                url = iri.replace('uri.interlex.org', self.host_port)
            else:
                url = f'http://{self.host_port}/base/curies/{curie}?local=True'
        elif label:
            url = f'http://{self.host_port}/base/lexical/{label}'
        else:
            return None

        if url in self._graph_cache:
            graph = self._graph_cache[url]
            if not graph:
                return None
        else:
            resp = get(url)
            if not resp.ok:
                self._graph_cache[url] = None
                return None
            ttl = resp.content
            graph = self.Graph().parse(data=ttl, format='turtle')
            self._graph_cache[url] = graph

        ia_iri = isAbout(graph)
        rdll = rdflibLocal(graph)

        if True:
            #qrs = rdll.query(label=label, predicates=predicates, all_classes=True)  # label=label issue?
            qrs = rdll.query(predicates=predicates, all_classes=True)
            qrd = {'predicates': {}}  # FIXME iri can be none?
            toskip = 'predicates',
            if curie is None and iri is None:
                i = OntId(ia_iri)
                qrd['curie'] = i.curie
                qrd['iri'] = i.iri
                toskip += 'curie', 'iri'
            if curie:
                qrd['curie'] = curie
                toskip += 'curie',
            if iri:
                qrd['iri'] = iri
                toskip += 'iri',

            for qr in qrs:
                #print(tc.ltgreen(str(qr)))
                # FIXME still last one wins behavior
                n = {k:v for k, v in qr.items()
                     if k not in toskip
                     and v is not None}
                qrd.update(n)
                qrd['predicates'].update(cullNone(**qr['predicates']))

            #print(tc.ltyellow(str(qrd)))
            yield QueryResult(kwargs, **qrd)

        else:
            # TODO cases where ilx is preferred will be troublesome
            maybe_out = [r for r in rdll.query(curie=curie, label=label, predicates=predicates)]
            if maybe_out:
                out = maybe_out
            else:
                out = rdll.query(iri=ia_iri, label=label, predicates=predicates)
                if curie:
                    for qr in out:
                        qr = cullNone(**qr)
                        yield QueryResult(kwargs, #qr._QueryResult__query_args,
                                          curie=curie,
                                          **{k:v for k, v in qr.items()
                                             if k != 'curie' })
                    return

            yield from out


class rdflibLocal(OntService):  # reccomended for local default implementation
    #graph = rdflib.Graph()  # TODO pull this out into ../plugins? package as ontquery-plugins?
    # if loading if the default set of ontologies is too slow, it is possible to
    # dump loaded graphs to a pickle gzip and distribute that with a release...

    def __init__(self, graph, OntId=OntId):
        self.OntId = OntId
        self.graph = graph
        try:
            self.predicate_mapping = {'label':rdflib.RDFS.label,}
        except NameError:
            raise ModuleNotFoundError('You need to install >=rdflib-5.0.0 to use this service') from rdflib_missing
        super().__init__()

    def add(self, iri, format):
        pass

    def setup(self):
        # graph is already set up...
        super().setup()

    @property
    def predicates(self):
        yield from sorted(set(self.graph.predicates()))

    def by_ident(self, iri, curie, kwargs):
        out = {'predicates':{}}
        identifier = self.OntId(curie=curie, iri=iri)
        gen = self.graph.predicate_objects(rdflib.URIRef(identifier))
        out['curie'] = identifier.curie
        out['iri'] = identifier.iri
        translate = {rdflib.RDFS.label:'label',
                        #rdflib.RDFS.subClassOf:'subClassOf',
                        #rdflib.RDF.type:'type',
                        #rdflib.OWL.disjointWith:'disjointWith',
                        #NIFRID.definingCitation:'definingCitation',
                    }
        o = None
        owlClass = None
        for p, o in gen:
            pn = translate.get(p, None)
            if isinstance(o, rdflib.Literal):
                o = o.toPython()
            elif p == rdflib.RDF.type and o == rdflib.OWL.Class:
                owlClass = True

            if pn is None:
                # TODO translation and support for query result structure
                # FIXME lists instead of klobbering results with mulitple predicates
                if isinstance(o, rdflib.URIRef):
                    o = self.OntId(o)  # FIXME we we try to use OntTerm directly everything breaks
                    # FIXME these OntIds also do not derive from rdflib... sigh
                out['predicates'][self.OntId(p).curie] = o  # curie to be consistent with OntTerm behavior
                #print(red.format('WARNING:'), 'untranslated predicate', p)
            else:
                out[pn] = o

        if o is not None and owlClass is not None:
            yield QueryResult(kwargs, **out, _graph=self.graph, source=self)  # if you yield here you have to yield from below

    def query(self, iri=None, curie=None, label=None, predicates=None, all_classes=False, **kwargs):
        # right now we only support exact matches to labels FIXME
        kwargs['curie'] = curie
        kwargs['iri'] = iri
        kwargs['label'] = label
        #kwargs['term'] = term
        #kwargs['search'] = search
        #supported = sorted(QueryResult(kwargs))
        if all_classes:
            for iri in self.graph[:rdflib.RDF.type:rdflib.OWL.Class]:
                if isinstance(iri, rdflib.URIRef):  # no BNodes
                    yield from self.by_ident(iri, None, kwargs)
        elif iri is not None or curie is not None:
            yield from self.by_ident(iri, curie, kwargs)
        else:
            for keyword, object in kwargs.items():
                if keyword in self.predicate_mapping:
                    predicate = self.predicate_mapping[keyword]
                    gen = self.graph.subjects(predicate, rdflib.Literal(object))
                    for subject in gen:
                        yield from self.query(iri=subject)
                        return  # FIXME we can only search one thing at a time... first wins


def main():
    import os
    from IPython import embed
    from pyontutils.namespaces import PREFIXES as uPREFIXES
    from pyontutils.config import get_api_key
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
    main()
