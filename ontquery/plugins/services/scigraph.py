import requests
import ontquery as oq
from ontquery.utils import cullNone, one_or_many, log, bunch, red
from ontquery.services import OntService
from . import deco, auth

try:
    from pyontutils import scigraph
except ModuleNotFoundError:
    from . import scigraph_client as scigraph
    deco.standalone_scigraph_api(scigraph.restService)
    deco.scigraph_api_key(scigraph.restService)


class SciGraphRemote(OntService):  # incomplete and not configureable yet
    cache = True
    verbose = False
    known_inverses = ('', ''),
    def __init__(self, apiEndpoint=None, OntId=oq.OntId):  # apiEndpoint=None -> default from pyontutils.devconfig
        try:
            requests
        except NameError:
            raise ModuleNotFoundError('You need to install requests to use this service') from requests_missing
        self.apiEndpoint = apiEndpoint
        self.OntId = OntId
        super().__init__()

    @property
    def readonly(self):
        return True

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

    def setup(self, **kwargs):

        self.sgv = scigraph.Vocabulary(cache=self.cache, verbose=self.verbose,
                                       basePath=self.apiEndpoint, safe_cache=True)
        self.sgg = scigraph.Graph(cache=self.cache, verbose=self.verbose,
                                  basePath=self.apiEndpoint)
        self.sgc = scigraph.Cypher(cache=self.cache, verbose=self.verbose,
                                   basePath=self.apiEndpoint)
        self.sgd = scigraph.Dynamic(cache=self.cache, verbose=self.verbose,
                                    basePath=self.apiEndpoint)
        self.curies = type('LocalCuries', (oq.OntCuries,), {})
        self._remote_curies = type('RemoteCuries', (oq.OntCuries.new(),), {})
        curies = self.sgc.getCuries()
        self.curies(curies)  # TODO can be used to provide curies...
        self._remote_curies(curies)
        self.prefixes = sorted(self.curies)
        self.search_prefixes = [p for p in sorted(self._remote_curies) if p != 'SCR']
        self.categories = self.sgv.getCategories()
        self._predicates = sorted(set(self.sgg.getRelationships()))
        #self._onts = sorted(o['n']['iri'] for o in self.sgc.execute('MATCH (n:Ontology) RETURN n', 1000, 'application/json'))  # only on newer versions, update when we switch production over
        self._onts = sorted(o['iri'] for o in
                            self.sgc.execute('MATCH (n:Ontology) RETURN n',
                                             1000,
                                             'text/plain'))
        super().setup(**kwargs)

    def _graphQuery(self, subject, predicate, depth=1, direction='OUTGOING',
                    entail=True, inverse=False, include_supers=False, done=None):
        # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
        # TODO how to handle depth? this is not an obvious or friendly way to do this
        if entail and inverse:
            raise NotImplementedError('Currently cannot handle inverse and entail at the same time.')

        if include_supers:
            if done is None:
                done = set()

            done.add(subject)
            for _, sup in self._graphQuery(subject, 'subClassOf', depth=40):
                if sup not in done:
                    done.add(sup)
                    for p, o in self._graphQuery(sup, predicate, depth=depth,
                                                 direction=direction, entail=entail,
                                                 inverse=inverse, done=done):
                        if o not in done:
                            done.add(o)
                            yield p, o

            for p, o in self._graphQuery(subject, predicate, depth=depth,
                                         direction=direction, entail=entail,
                                         inverse=inverse, done=done):
                if o not in done:
                    yield p, o
                    done.add(o)
                    yield from self._graphQuery(o, predicate, depth=depth,
                                                direction=direction, entail=entail,
                                                inverse=inverse, include_supers=include_supers, done=done)
            return

        d_nodes_edges = self.sgg.getNeighbors(subject, relationshipType=predicate,
                                              depth=depth, direction=direction, entail=entail)  # TODO

        if d_nodes_edges:
            edges = d_nodes_edges['edges']
        else:
            if inverse:  # it is probably a bad idea to try to be clever here AND INDEED IT HAS BEEN
                predicate = self.inverses[predicate]

            _p = (predicate.curie
                  if hasattr(predicate, 'curie') and predicate.curie is not None
                  else predicate)
            log.warning(f'{subject.curie} has no edges with predicate {_p} ')
            return

        s, o = 'sub', 'obj'
        if inverse:
            s, o = o, s

        def properPredicate(e):
            if ':' in e['pred']:
                p = self.OntId(e['pred'])
                if inverse:  # FIXME p == predicate ? no it is worse ...
                    p = self.inverses[p]

                p = p.curie
            else:
                p = e['pred']

            return p

        if depth > 1:
            #subjects = set(subject.curie)
            seen = {((predicate.curie if isinstance(predicate, self.OntId) else predicate),
                     subject.curie)}
            for i, e in enumerate(self.sgg.ordered(subject.curie, edges, inverse=inverse)):
                if [v for k, v in e.items() if k != 'meta' and v.startswith('_:')]:
                    # FIXME warn on these ? bnode getting pulled in ...
                    # argh ... this is annoying to deal with
                    continue
                #print('record number:', i)  # FIXME
                # FIXME need to actually get the transitive closure, this doesn't actually work
                #if e[s] in subjects:
                    #subjects.add(object.curie)
                object = e[o]
                p = e['pred']  # required if entail == True
                if (p, object) not in seen:
                    # to make OntTerm(object) work we need to be able to use the 'meta' section...
                    # and would have to fetch the object directly anyway since OntTerm requires
                    # direct atestation ... which suggests that we probably need/want a bulk constructor
                    seen.add((p, object))
                    yield (properPredicate(e),
                           self.OntId(object)) # FIXME TODO this is _very_ inefficient for multiple lookups...

        else:
            _has_part_list = ['http://purl.obolibrary.org/obo/BFO_0000051']
            _disjoint_with_list = ['disjointWith']
            scurie = self._remote_curies.qname(subject)
            pred_objects = ((properPredicate(e),
                             self.OntId(e[o])) for e in edges if e[s] == scurie
                            #and not print(predicate, scurie, e['pred'], e[o])
                            and not [v for k, v in e.items()
                                     if k != 'meta' and v.startswith('_:')]
                            and ('owlType' not in e['meta'] or
                                 (e['meta']['owlType'] != _has_part_list and
                                  e['meta']['owlType'] != _disjoint_with_list)))
            yield from pred_objects

    def query(self, iri=None, curie=None,
              label=None, term=None, search=None, abbrev=None,  # FIXME abbrev -> any?
              prefix=tuple(), category=tuple(), exclude_prefix=tuple(),
              include_deprecated=False, include_supers=False,
              predicates=tuple(), depth=1,
              direction='OUTGOING', entail=True, limit=10):
        # BEWARE THE MADNESS THAT LURKS WITHIN
        def herp(p):
            if hasattr(p, 'curie'):
                return self.OntId(p)
            elif ':' in p:
                return self.OntId(p)
            elif type(p) == str:
                return p
            else:
                raise TypeError(f'wat {type(p)} {p}')

        def derp(ps):
            for p in ps:
                if hasattr(p, 'curie'):
                    if p.curie:
                        yield p.curie
                    else:
                        yield str(p)
                else:
                    yield p

        # use explicit keyword arguments to dispatch on type
        prefix = one_or_many(prefix)
        category = one_or_many(category)

        bads = [p for p in prefix if p not in self.curies]
        if prefix and bads:
            raise ValueError(f'None of {bads} in {self.__class__.__name__}.prefixes')

        if category and [c for c in category if c not in self.categories]:
            raise ValueError(f'{category} not in {self.__class__.__name__}.categories')

        if (not prefix and
            any((label, term, search, abbrev)) and
            self.prefixes != self.search_prefixes):
            prefix = self.search_prefixes

        if exclude_prefix:
            to_exclude = set(self.curies.qname(ep)
                             for p in exclude_prefix
                             for ep in self.curies.identifier_prefixes(p))
            prefix = tuple(p for p in prefix if p not in to_exclude)

        search_expressions = cullNone(label=label,
                                      term=term,
                                      search=search,
                                      abbrev=abbrev)
        qualifiers = cullNone(prefix=prefix,
                              category=category,
                              limit=limit)
        identifiers = cullNone(iri=iri, curie=curie)
        predicates = tuple(herp(p) for p in predicates)

        out_predicates = []
        if identifiers:
            identifier = self.OntId(next(iter(identifiers.values())))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # this does not accept qualifiers
            # WARNING
            # if results are cached then the mutation we do below
            # mutates the cache and makes things into OntIds when
            # other parts of the code expects strings
            # this is fixed in scigraph client
            if result is None:
                return

            if predicates:  # TODO incoming/outgoing, 'ALL' by depth to avoid fanout
                short = None
                for predicate in predicates:
                    if (hasattr(predicate, 'prefix') and
                        predicate.prefix in ('owl', 'rdfs')):
                        unshorten = next(derp([predicate]))
                        predicate = predicate.suffix
                    else:
                        unshorten = None

                    ptest = predicate.curie if isinstance(predicate, self.OntId) else predicate

                    #log.debug(repr(predicate))
                    values = tuple(sorted(self._graphQuery(identifier, predicate, depth=depth,
                                                           direction=direction, entail=entail,
                                                           include_supers=include_supers)))
                    if values:
                        # FIXME when using query.predicates need to 'expand'
                        # the bare string predicates like subClassOf and isDefinedBy ...
                        bunched = bunch(values)
                        for pred, pvalues in bunched.items():
                            # I think this is the right place to unshorten
                            # I don't think we have any inverses that require unshortning
                            if pred == ptest:
                                if unshorten is not None:
                                    short = predicate
                                    predicate = unshorten
                                    pred = predicate

                            out_predicates.append(pred)
                            result[pred] = tuple(pvalues)

                    if predicate in self.inverses:
                        p = self.inverses[predicate]
                        inv_direction = ('OUTGOING' if
                                         direction == 'INCOMING' else
                                         ('INCOMING' if
                                          direction == 'OUTGOING'
                                          else direction))

                        # FIXME I'm betting reverse entailed is completely broken
                        inv_values = tuple(sorted(self._graphQuery(identifier, p,
                                                                   depth=depth, direction=inv_direction,
                                                                   entail=False, inverse=True,
                                                                   include_supers=include_supers)))  # FIXME entail=entail
                        if inv_values:
                            bunched = bunch(inv_values)
                            for pred, ipvalues in bunched.items():
                                if short is not None and pred == short:
                                    pred = predicate

                                if pred in result:
                                    rp = result[pred]
                                    fv = tuple(v for v in ipvalues if v not in rp)
                                    result[pred] += fv
                                else:
                                    result[pred] = tuple(ipvalues)
                                    out_predicates.append(pred)

            res = self.sgg.getNode(identifier)
            types = tuple()
            _type = None
            for _type in res['nodes'][0]['meta']['types']:
                if _type not in result['categories']:
                    _type = self.OntId('owl:' + _type)
                    types += _type,

            result['type'] = types[0] if _type is not None else None
            result['types'] = types

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
            if not include_deprecated and result['deprecated'] and not identifiers:
                continue
            ni = lambda i: next(iter(sorted(i))) if i else None  # FIXME multiple labels issue
            predicate_results = {predicate:result[predicate]  # FIXME hack
                                 for predicate in derp(out_predicates)  # TODO depth=1 means go ahead and retrieve?
                                 if predicate in result}  # FIXME hasheqv on OntId

            #print(red.format('PR:'), pprint.pformat(predicate_results), pprint.pformat(result))
            yield self.QueryResult(
                query_args={**search_expressions,
                            **qualifiers,
                            **identifiers,
                            'predicates':predicates},
                iri=result['iri'],
                curie=result['curie'] if 'curie' in result else None,
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
                type=result['type'] if 'type' in result else None,
                types=result['types'] if 'types' in result else tuple(),
                source=self)

            if count >= limit:  # FIXME deprecated issue
                break
            else:
                count += 1


class SciCrunchRemote(SciGraphRemote):
    known_inverses = ('partOf:', 'hasPart:'),
    defaultEndpoint = auth.get_default('standalone-scigraph-api')
    def __init__(self, apiEndpoint=auth.get('standalone-scigraph-api'), OntId=oq.OntId):
        super().__init__(apiEndpoint=apiEndpoint, OntId=OntId)

    def setup(self, **kwargs):
        if scigraph.restService.api_key is None and self.apiEndpoint == self.defaultEndpoint:
            raise ValueError('You have not set an API key for the SciCrunch API!')

        super().setup(**kwargs)

    def termRequest(self, term):
        if term.validated:
            raise TypeError('Can\'t add a term that already exists!')

        log.info('It seems that you have found a terms that is not in your remote! '
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
                    log.error('This term has already been requested')

            def url_link(self):
                return post_template + 'TODO-TODO-TODO'

