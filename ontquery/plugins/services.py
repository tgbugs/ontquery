import os
import ontquery.exceptions as exc
from ontquery import OntCuries, OntId
from ontquery.utils import cullNone, one_or_many, log
from ontquery.services import OntService
from .interlex_client import InterLexClient

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

_empty_tuple = tuple()


class SciGraphRemote(OntService):  # incomplete and not configureable yet
    cache = True
    verbose = False
    known_inverses = ('', ''),
    def __init__(self, apiEndpoint=None, OntId=OntId):  # apiEndpoint=None -> default from pyontutils.devconfig
        try:
            requests
        except NameError:
            raise ModuleNotFoundError('You need to install requests to use this service') from requests_missing
        self.apiEndpoint = apiEndpoint
        self.api_key = os.environ.get('SCIGRAPH_API_KEY', None)
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
        # TODO make it possible to set these properties dynamically
        # one way is just to do scigraph = SciGraphRemote \\ OntQuery(scigraph)
        self.sgv = scigraph.Vocabulary(cache=self.cache, verbose=self.verbose,
                                       basePath=self.apiEndpoint, key=self.api_key)
        self.sgg = scigraph.Graph(cache=self.cache, verbose=self.verbose,
                                  basePath=self.apiEndpoint, key=self.api_key)
        self.sgc = scigraph.Cypher(cache=self.cache, verbose=self.verbose,
                                   basePath=self.apiEndpoint, key=self.api_key)
        self.curies = type('LocalCuries', (OntCuries,), {})
        self.curies(self.sgc.getCuries())  # TODO can be used to provide curies...
        self.prefixes = sorted(self.curies)
        self.search_prefixes = [p for p in self.prefixes if p != 'SCR']
        self.categories = self.sgv.getCategories()
        self._predicates = sorted(set(self.sgg.getRelationships()))
        #self._onts = sorted(o['n']['iri'] for o in self.sgc.execute('MATCH (n:Ontology) RETURN n', 1000, 'application/json'))  # only on newer versions, update when we switch production over
        self._onts = sorted(o['iri'] for o in
                            self.sgc.execute('MATCH (n:Ontology) RETURN n',
                                             1000,
                                             'text/plain'))
        super().setup(**kwargs)

    def _graphQuery(self, subject, predicate, depth=1, direction='OUTGOING', inverse=False):
        # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
        # TODO how to handle depth? this is not an obvious or friendly way to do this

        d_nodes_edges = self.sgg.getNeighbors(subject, relationshipType=predicate,
                                              depth=depth, direction=direction)  # TODO

        if d_nodes_edges:
            edges = d_nodes_edges['edges']
        else:
            if inverse:  # it is probably a bad idea to try to be clever here
                predicate = self.inverses[predicate]

            log.warning(f'{subject.curie} has no edges with predicate {predicate.curie} ')
            return

        s, o = 'sub', 'obj'
        if inverse:
            s, o = o, s

        if depth > 1:
            #subjects = set(subject.curie)
            seen = {subject.curie}
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
                if object not in seen:
                    # to make OntTerm(object) work we need to be able to use the 'meta' section...
                    # and would have to fetch the object directly anyway since OntTerm requires
                    # direct atestation ... which suggests that we probably need/want a bulk constructor
                    seen.add(object)
                    yield self.OntId(object) # FIXME TODO this is _very_ inefficient for multiple lookups...

        else:
            objects = (self.OntId(e[o]) for e in edges if e[s] == subject.curie
                       and not [v for k, v in e.items()
                                if k != 'meta' and v.startswith('_:')])
            yield from objects

    def query(self, iri=None, curie=None,
              label=None, term=None, search=None, abbrev=None,  # FIXME abbrev -> any?
              prefix=tuple(), category=tuple(), exclude_prefix=tuple(),
              predicates=tuple(), depth=1,
              direction='OUTGOING', limit=10):
        # use explicit keyword arguments to dispatch on type
        prefix = one_or_many(prefix)
        category = one_or_many(category)

        if prefix and [p for p in prefix if p not in self.curies]:
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
        predicates = tuple(self.OntId(p)
                           if not isinstance(p, self.OntId) and ':' in p
                           else p for p in predicates)
        if identifiers:
            identifier = self.OntId(next(iter(identifiers.values())))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # this does not accept qualifiers
            if result is None:
                return

            if predicates:  # TODO incoming/outgoing, 'ALL' by depth to avoid fanout
                for predicate in predicates:
                    if predicate.prefix in ('owl', 'rdfs'):
                        unshorten = predicate
                        predicate = predicate.suffix
                    else:
                        unshorten = None

                    values = tuple(sorted(self._graphQuery(identifier, predicate,
                                                           depth=depth, direction=direction)))
                    if values:
                        # I think this is the right place to unshorten
                        # I don't think we have any inverses that require unshortning
                        if unshorten is not None:
                            short = predicate
                            predicate = unshorten

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
            if result['deprecated'] and not identifiers:
                continue
            ni = lambda i: next(iter(sorted(i))) if i else None  # FIXME multiple labels issue
            predicate_results = {predicate.curie if ':' in predicate else predicate:result[predicate]  # FIXME hack
                                 for predicate in predicates  # TODO depth=1 means go ahead and retrieve?
                                 if predicate in result}  # FIXME hasheqv on OntId
            # print(red.format('PR:'), predicate_results, result)
            yield self.QueryResult(
                query_args={**search_expressions,
                            **qualifiers,
                            **identifiers,
                            'predicates':predicates},
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
                type=result['type'] if 'type' in result else None,
                types=result['types'] if 'types' in result else tuple(),
                source=self)

            if count >= limit:  # FIXME deprecated issue
                break
            else:
                count += 1


class SciCrunchRemote(SciGraphRemote):
    known_inverses = ('partOf:', 'hasPart:'),
    defaultEndpoint = 'https://scicrunch.org/api/1/sparc-scigraph'
    def __init__(self, apiEndpoint=defaultEndpoint, OntId=OntId):
        super().__init__(apiEndpoint=apiEndpoint, OntId=OntId)
        if self.api_key is None:
            self.api_key = os.environ.get('SCICRUNCH_API_KEY', None)

    def setup(self, **kwargs):
        if self.api_key is None and self.apiEndpoint == self.defaultEndpoint:
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


class _InterLexSharedCache:
    _graph_cache = {}
    # FIXME maxsize ??


class InterLexRemote(_InterLexSharedCache, OntService):  # note to self
    known_inverses = ('', ''),
    defaultEndpoint = 'https://scicrunch.org/api/1/'
    def __init__(self, *args, apiEndpoint=defaultEndpoint,
                 host='uri.interlex.org', port='',
                 user_curies: dict={'ILX', 'http://uri.interlex.org/base/ilx_'},  # FIXME hardcoded
                 readonly=False,
                 **kwargs):
        """ user_curies is a local curie mapping from prefix to a uri
            This usually is a full http://uri.interlex.org/base/ilx_1234567 identifier """

        self.api_key = os.environ.get('INTERLEX_API_KEY', os.environ.get('SCICRUNCH_API_KEY', None))

        if self.api_key is None and apiEndpoint == self.defaultEndpoint:
            # we don't error here because API keys are not required for viewing
            log.warning('You have not set an API key for the SciCrunch API!')

        self.apiEndpoint = apiEndpoint

        try:
            requests
        except NameError:
            msg = 'You need to install requests to use this service'
            raise ModuleNotFoundError(msg) from requests_missing

        self.host = host
        self.port = port
        self.user_curies = user_curies
        self.readonly = readonly

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

    def setup(self, **kwargs):
        OntCuries({'ILXTEMP':'http://uri.interlex.org/base/tmp_'})
        if self.api_key is not None and self.apiEndpoint is not None:
            self.ilx_cli = InterLexClient(base_url=self.apiEndpoint)
        elif not self.readonly:
            # expect attribute errors for ilx_cli

            log.warning('You have not set an API key for the SciCrunch API! '
                        'InterLexRemote will error if you try to use it.')

        super().setup(**kwargs)

    @property
    def host_port(self):
        return f'{self.host}:{self.port}' if self.port else self.host

    @property
    def predicates(self):
        return {}  # TODO

    def add_class(self,
                  subClassOf=None,
                  label=None,
                  definition=None,
                  synonyms=tuple(),
                  comment=None,
                  predicates: dict=None):
        return self.add_entity('term', subClassOf, label, definition, synonyms, comment, predicates)

    def add_pde(self,
                label,
                definition:str=None,
                synonyms=tuple(),
                comment: str=None,
                predicates: dict=None):
        return self.add_entity(
            type = 'pde',
            label = label,
            subThingOf = None,  # FIXME works for now
            definition = definition,
            synonyms = synonyms,
            comment = comment,
            predicates = predicates)

    def add_predicates(self, ilx_curieoriri: str, predicate_objects_dict: dict) -> list:
        tresp = []
        if not ilx_curieoriri.startswith('http://uri.interlex.org/base/'): # FIXME: need formality
            subject = 'http://uri.interlex.org/base/' + ilx_curieoriri
        else:
            subject = ilx_curieoriri
        for predicate, objs in predicate_objects_dict.items():
            if not isinstance(objs, list):
                objs = [objs]
            for object in objs:
                # server output doesnt include their ILX IDs ... so it's not worth getting
                tresp.append(self.add_triple(subject, predicate, object))
                # TODO stick the responding predicates etc in if success
        return tresp

    def delete_predicates(self, ilx_curieoriri: str, predicate_objects_dict: dict) -> list:
        tresp = []
        if not ilx_curieoriri.startswith('http://uri.interlex.org/base/'): # FIXME: need formality
            subject = 'http://uri.interlex.org/base/' + ilx_curieoriri
        else:
            subject = ilx_curieoriri
        for predicate, objs in predicate_objects_dict.items():
            if not isinstance(objs, list):
                objs = [objs]
            for object in objs:
                # server output doesnt include their ILX IDs ... so it's not worth getting
                tresp.append(self.delete_triple(subject, predicate, object))
                # TODO stick the responding predicates etc in if success
        return tresp

    def add_entity(self, type, subThingOf, label, definition: str=None,
                   synonyms=tuple(), comment: str=None, predicates: dict=None):

        if self.readonly:
            raise exc.ReadOnlyError('InterLexRemote is in readonly mode.')

        resp = self.ilx_cli.add_entity(
            label = label,
            type = type,
            superclass = subThingOf,
            definition = definition,
            comment = comment,
            synonyms = synonyms,
        )
        out_predicates = {}

        if predicates:
            tresp = self.add_predicates(ilx_curieoriri=resp['ilx'], predicate_objects_dict=predicates)
            resp['annotations'] = tresp # TODO: Creates a record for annotations in term_versions table

        if 'comment' in resp:  # filtering of missing fields is done in the client
            out_predicates['comment'] = resp['comment']

        return self.QueryResult(
            query_args = {},
            iri=resp['iri'],
            curie=resp['curie'],
            label=resp['label'],
            labels=tuple(),
            #abbrev=None,  # TODO
            #acronym=None,  # TODO
            definition=resp.get('definition', None),
            synonyms=tuple(resp.get('synonyms', tuple())),
            #deprecated=None,
            #prefix=None,
            #category=None,
            predicates=out_predicates,
            #_graph=None,
            source=self,
        )

    def update_entity(self, ilx_id: str=None, type: str=None, subThingOf: str=None, label: str=None,
                      definition: str=None, synonyms=tuple(), comment: str=None,
                      predicates_to_add: dict=None, predicates_to_delete: dict=None):

        resp = self.ilx_cli.update_entity(
            ilx_id = ilx_id,
            label = label,
            type = type,
            superclass = subThingOf,
            definition = definition,
            comment = comment,
            synonyms = synonyms,
            # predicates = tresp,
        )

        tresp = None
        if predicates_to_add:
            trep = self.add_predicates(ilx_curieoriri=resp['ilx'], predicate_objects_dict=predicates_to_add)

        tresp = None
        if predicates_to_delete:
            trep = self.delete_predicates(ilx_curieoriri=resp['ilx'], predicate_objects_dict=predicates_to_delete)

        out_predicates = {}
        if 'comment' in resp:  # filtering of missing fields is done in the client
            out_predicates['comment'] = resp['comment']

        return self.QueryResult(
             query_args = {},
             iri=resp['iri'],
             curie=resp['curie'],
             label=resp['label'],
             labels=tuple(),
             #abbrev=None, # TODO
             #acronym=None, # TODO
             definition=resp['definition'],
             synonyms=tuple(resp['synonyms']),
             #deprecated=None,
             #prefix=None,
             #category=None,
             predicates=out_predicates,
             #_graph=None,
             source=self,
        )

    def add_triple(self, subject, predicate, object):
        """ Triple of curied or full iris to add to graph.
            Subject should be an interlex"""

        def filter_ontid(ontid):
            if ontid.startswith('http://'):
                pass
            elif ontid.prefix == 'ILXTEMP':
                ontid = 'tmp_' + ontid.suffix
            else:
                ontid = 'ilx_' + ontid.suffix
            return ontid

        # this split between annotations and relationships is severely annoying
        # because you have to know before hand which one it is (sigh)
        s = OntId(subject)
        p = OntId(predicate)
        o = self._get_type(object)
        if type(o) == str:
            func = self.ilx_cli.add_annotation
        elif type(o) == OntId:
            func = self.ilx_cli.add_relationship
            o = filter_ontid(o)
        else:
            raise TypeError(f'what are you giving me?! {object!r}')

        s = filter_ontid(s)
        p = filter_ontid(p)

        resp = func(s, p, o)
        return resp

    def delete_triple(self, subject, predicate, object):
        """ Triple of curied or full iris to add to graph.
            Subject should be an interlex"""

        def filter_ontid(ontid):
            if ontid.startswith('http://'):
                pass
            elif ontid.prefix == 'ILXTEMP':
                ontid = 'tmp_' + ontid.suffix
            else:
                ontid = 'ilx_' + ontid.suffix
            return ontid

        # this split between annotations and relationships is severely annoying
        # because you have to know before hand which one it is (sigh)
        s = OntId(subject)
        p = OntId(predicate)
        o = self._get_type(object)
        if type(o) == str:
            func = self.ilx_cli.delete_annotation
        elif type(o) == OntId:
            func = self.ilx_cli.delete_relationship
            o = filter_ontid(o)
        else:
            raise TypeError(f'what are you giving me?! {object!r}')

        s = filter_ontid(s)
        p = filter_ontid(p)

        # TODO: check if add_relationship works
        resp = func(s, p, o)
        return resp

    def _get_type(self, entity):
        try:
            return OntId(entity)
        except OntId.Error:
            return entity

    def query(self, iri=None, curie=None, label=None, term=None, predicates=None,
              prefix=tuple(), exclude_prefix=tuple(), **_):
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
            if ttl.startswith(b'<!DOCTYPE HTML PUBLIC'):
                return None  # FIXME disambiguation multi results page

            graph = self.Graph().parse(data=ttl, format='turtle')
            self._graph_cache[url] = graph

        ia_iri = isAbout(graph)
        i = OntId(ia_iri)
        if exclude_prefix and i.prefix in exclude_prefix:
            return None

        if prefix and i.prefix not in prefix:  # FIXME alternate ids ...
            return None

        rdll = rdflibLocal(graph)
        rdll.setup(instrumented=self.OntTerm)

        if True:
            #qrs = rdll.query(label=label, predicates=predicates, all_classes=True)  # label=label issue?
            qrs = rdll.query(predicates=predicates, all_classes=True)
            qrd = {'predicates': {}}  # FIXME iri can be none?
            toskip = 'predicates',
            if curie is None and iri is None:
                #i = OntId(ia_iri)
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

            qrd['source'] = self
            #print(tc.ltyellow(str(qrd)))
            yield self.QueryResult(kwargs, **qrd)

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
                        yield self.QueryResult(kwargs, #qr._QueryResult__query_args,
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
        self._curies = {cp:ip for cp, ip in self.graph.namespaces()}
        try:
            self.predicate_mapping = {'label': (rdflib.RDFS.label,),
                                      'term': (rdflib.RDFS.label,
                                               rdflib.URIRef(self.OntId('skos:prefLabel')),
                                               rdflib.URIRef(self.OntId('skos:altLabel')),
                                               rdflib.URIRef(self.OntId('skos:hiddenLabel')),
                                               rdflib.URIRef(self.OntId('NIFRID:synonym')),
                                               rdflib.URIRef(self.OntId('oboInOwl:hasSynonym')),
                                               rdflib.URIRef(self.OntId('oboInOwl:hasExactSynonym')),
                                               rdflib.URIRef(self.OntId('oboInOwl:hasNarroSynonym')),
                                      ),
            }
        except NameError:
            msg = 'You need to install >=rdflib-5.0.0 to use this service'
            raise ModuleNotFoundError(msg) from rdflib_missing

        super().__init__()

    @property
    def _onts(self):
        yield from self.graph[:rdflib.RDF.type:rdflib.OWL.Ontology]

    def add(self, iri, format):
        pass

    def setup(self, **kwargs):
        # graph is already set up...
        # assume that the graph is static for these
        super().setup(**kwargs)

    @property
    def curies(self):
        return self._curies

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
        owl = rdflib.OWL
        for p, o in gen:
            if isinstance(o, rdflib.BNode):
                continue

            pn = translate.get(p, None)
            if isinstance(o, rdflib.Literal):
                o = o.toPython()

            #elif p == rdflib.RDF.type and o == owl.Class:
            elif p == rdflib.RDF.type and o in (owl.Class, owl.ObjectProperty,
                                                owl.DatatypeProperty, owl.AnnotationProperty):
                if 'type' not in out:
                    out['type'] = o  # FIXME preferred type ...
                else:
                    if 'types' not in out:
                        out['types'] = out['type'],

                    out['types'] += o

                owlClass = True  # FIXME ...

            if pn is None:
                # TODO translation and support for query result structure
                # FIXME lists instead of klobbering results with mulitple predicates
                if isinstance(o, rdflib.URIRef):
                    o = self.OntId(o)  # FIXME we try to use OntTerm directly everything breaks
                    # FIXME these OntIds also do not derive from rdflib... sigh
                # FIXME doesn't this klobber when there is more than one object per predicate !??!? !??!!
                out['predicates'][self.OntId(p).curie] = o  # curie to be consistent with OntTerm behavior
                #print(red.format('WARNING:'), 'untranslated predicate', p)
            else:
                out[pn] = o

        if o is not None and owlClass is not None:
            # if you yield here you have to yield from below
            yield self.QueryResult(kwargs, **out, _graph=self.graph, source=self)

    def _prefix(self, iri):
        try:
            prefix, _, _ = self.graph.compute_qname(iri, generate=False)
            return prefix
        except KeyError:
            return None

    def query(self, iri=None, curie=None, label=None, term=None, predicates=None,
              search=None, prefix=tuple(), exclude_prefix=tuple(), all_classes=False, **kwargs):
        if (prefix is not None and
            prefix is not _empty_tuple and
            all(a is None for a in (iri, curie, label, term))):
            if isinstance(prefix, str):
                prefix = prefix,

            for p in prefix:
                iri_prefix = self.graph.namespace_manager.store.namespace(p)
                if iri_prefix is not None:
                    # TODO is this faster or is shortening? this seems like it might be faster ...
                    # unless the graph has it all cached
                    for _iri in sorted(u for u in set(e for t in self.graph for e in t
                                                if isinstance(e, rdflib.URIRef))
                                       if self._prefix(u) == p):
                        yield from self.query(iri=_iri)

            return

        # right now we only support exact matches to labels FIXME
        kwargs['curie'] = curie
        kwargs['iri'] = iri
        kwargs['label'] = label
        kwargs['term'] = term

        #kwargs['term'] = term
        #kwargs['search'] = search
        #supported = sorted(self.QueryResult(kwargs))
        if all_classes:
            for iri in self.graph[:rdflib.RDF.type:rdflib.OWL.Class]:
                if isinstance(iri, rdflib.URIRef):  # no BNodes
                    yield from self.by_ident(iri, None, kwargs)  # actually query is done here
        elif iri is not None or curie is not None:
            yield from self.by_ident(iri, curie, kwargs)
        else:
            for keyword, object in kwargs.items():
                if object is None:
                    continue

                if keyword in self.predicate_mapping:
                    predicates = self.predicate_mapping[keyword]
                    for predicate in predicates:
                        gen = self.graph.subjects(predicate, rdflib.Literal(object))
                        for subject in gen:
                            if prefix or exclude_prefix:
                                oid = self.OntId(subject)
                                if prefix and oid.prefix not in prefix:
                                    continue

                                if exclude_prefix and oid.prefix in exclude_prefix:
                                    continue

                            yield from self.query(iri=subject)
                            return  # FIXME we can only search one thing at a time... first wins


class StaticIrisRemote(rdflibLocal):
    """ Create a Local from a remote by fetching the content at that iri """
    persistent_cache = False  # TODO useful for nwb usecase
    def __init__(self, *iris, OntId=OntId):
        self.graph = rdflib.ConjunctiveGraph()
        for iri in iris:
            # TODO filetype detection from interlex
            resp = requests.get(iri)
            if resp.ok:
                ttl = resp.content
                self.graph.parse(data=ttl, format='turtle')
            else:
                raise exc.FetchingError(f'Could not fetch {iri} {resp.status_code} {resp.reason}')

        super().__init__(self.graph, OntId=OntId)


class GitHubRemote(StaticIrisRemote):  # TODO very incomplete
    """ Create a Local from a file on github from group, repo, and filename """
    base_iri = ('https://raw.githubusercontent.com/'
                '{group}/{repo}/{branch_or_commit}/{filepath}')
    def __init__(self, group, repo, *filepaths,
                 branch='master',
                 commit=None,  # mutually exclusive with branch, or error on commit not on branch?
                 branches_or_commits=('master',),
                 OntId=OntId):
        """ filepath from the working directory no leading slash """
        # TODO > 1 group, there are too many combinations here
        # use case would be to load all the relevant files from each of the
        # branches parcellation, neurons, methods, sparc
        # to do this with scigraph we could have a function that produced
        # the yaml template that loads the output of self.iris
        self.filepaths = filepaths
        self.groups_repos_branches = (group, repo, branch),
        super().__init__(*self.iris, OntId=OntId)

    @property
    def iris(self):
        for group, repo, branch_or_commit in self.groups_repos_branches:
            for filepath in self.filepaths:
                yield self.base_iri.format(group=group,
                                           repo=repo,
                                           branch_or_commit=branch_or_commit,
                                           filepath=filepath)


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
    #main()
