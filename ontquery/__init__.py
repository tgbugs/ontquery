from collections import UserDict
from six import text_type
from inspect import signature
from urllib import parse
from IPython import embed

red = '\x1b[91m{}\x1b[0m'

def cullNone(**kwargs):
    return {k:v for k, v in kwargs.items() if v is not None}

class QueryResult:
    """ Encapsulate query results and allow for clear and clean documentation
        of how a particular service maps their result terminology onto the
        ontquery keyword api. """
    def __init__(self,
                 query_args,
                 iri=None,
                 curie=None,
                 label=None,
                 abbrev=None,  # TODO
                 acronym=None,  # TODO
                 definition=None,
                 synonyms=None,
                 prefix=None,
                 category=None,
                 predicates=None,
                 upstream=None):
        self.__query_args = query_args  # for debug
        self.__dict = {}
        if upstream is None:
            self.__upstream = OntTerm
        else:
            self.__upstream = upstream
        for k, v in dict(iri=iri,
                         curie=curie,
                         label=label,
                         definition=definition,
                         synonyms=synonyms,
                         predicates=predicates).items():
            # this must return the empty values for all keys
            # so that users don't have to worry about hasattring
            # to make sure they aren't about to step into a typeless void
            setattr(self, k, v)
            self.__dict[k] = v
            #self.__dict__[k] = v

    def asTerm(self):  # FIXME does not work as desired
        return self.__upstream(iri=self.iri)  # TODO works best with a cache

    def keys(self):
        yield from self.__dict.keys()

    def values(self):
        yield from self.__dict.values()

    def items(self):
        yield from self.__dict.items()

    def __iter__(self):
        yield from self.__dict

    def __getitem__(self, key):
        try:
            return self.__dict[key]
        except KeyError as e:
            self.__missing__(key, e)

    def __contains__(self, key):
        return key in self.__dict

    def __missing__(self, key, e=None):
        raise KeyError(f'{key} {type(key)}') from e

    def __setitem__(self, key, value):
        raise ValueError('Cannot set results of a query.')

    def __repr__(self):
        return f'QueryResult({self.__dict!r})'


class OntCuries:
    """ A bad implementation of a singleton dictionary based namespace.
        Probably better to use metaclass= to init this so types can be tracked.
    """
    # TODO how to set an OntCuries as the default...
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_' + cls.__name__ + '__dict'):
            cls.__dict = {}
        cls.__dict.update(dict(*args, **kwargs))
        return cls.__dict

    @classmethod
    def qname(cls, iri):
        # sort in reverse to match longest matching namespace first TODO/FIXME trie
        for prefix, namespace in sorted(cls.__dict.items(), key=lambda kv: len(kv[1]), reverse=True):
            if iri.startswith(namespace):
                suffix = iri[len(namespace):]
                return ':'.join((prefix, suffix))
        return iri


class OntId(text_type):  # TODO all terms singletons to prevent nastyness
    _namespaces = OntCuries  # overwrite when subclassing to switch curies...
    repr_arg_order = (('curie',),
                      ('prefix', 'suffix'),
                      ('iri',))
    __firsts = 'curie', 'iri'
    def __new__(cls, curie_or_iri=None, prefix=None, suffix=None, curie=None, iri=None, **kwargs):

        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            cls.__repr_level = 0
            if not hasattr(cls, 'repr_args'):
                cls.repr_args = cls.repr_arg_order[0]

        iri_ps, iri_ci, iri_c = None, None, None

        if prefix is not None and suffix is not None:
            #curie_ps = ':'.join(prefix, suffix)
            iri_ps = cls._make_iri(prefix, suffix)

        if curie_or_iri is not None:
            if (curie_or_iri.startswith('http://') or
                curie_or_iri.startswith('https://') or 
                curie_or_iri.startswith('file://')):
                iri_ci = curie_or_iri
                curie_ci = cls._namespaces.qname(iri_ci)
                prefix, suffix = curie_ci.split(':')
            else:
                curie_ci = curie_or_iri
                try:
                    prefix, suffix = curie_ci.split(':')
                except ValueError as e:
                    raise ValueError(f'Could not split cuire {curie_ci!r} is it actually an identifier?') from e
                iri_ci = cls._make_iri(prefix, suffix)

        if curie is not None and curie != iri:
            prefix, suffix = curie.split(':')
            iri_c = cls._make_iri(prefix, suffix)

        if iri is not None:
            curie_i = cls._namespaces.qname(iri)
            prefix, suffix = curie_i.split(':')

        iris = iri_ps, iri_ci, iri_c, iri
        unique_iris = set(i for i in iris if i is not None)

        if len(unique_iris) > 1:
            ValueError(f'All ways of constructing iris not match! {sorted(unique_iris)}')
        else:
            iri = next(iter(unique_iris))

        self = super().__new__(cls, iri)
        self.prefix = prefix
        self.suffix = suffix
        return self

    @property
    def namespaces(self):
        return self._namespaces()

    @namespaces.setter
    def namespaces(self, value):
        self.__class__._namespaces = value
        # TODO recompute prefix and suffix for the new namespaces for all subclasses.
        # even though this is a property

    @property
    def curie(self):
        return ':'.join((self.prefix, self.suffix))

    @property
    def iri(self):
        return str(self)  # without str we will get infinite recursion

    @classmethod
    def _make_iri(cls, prefix, suffix):
        namespaces = cls._namespaces()
        if prefix in namespaces:
            return namespaces[prefix] + suffix
        else:
            raise KeyError(f'Unknown curie prefix: {prefix}')

    @classmethod
    def repr_level(cls):  # FIXME naming
        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            setattr(cls, f'_{cls.__name__}__repr_level', 0)
            #cls.__repr_level = 0 # how is this different....
        current = getattr(cls, f'_{cls.__name__}__repr_level')
        nargs = len(cls.repr_arg_order)
        next = (current + 1) % nargs
        cls.repr_args = self.repr_arg_order[next]
        print(self.__name__, 'will now repr with', cls.repr_args)
        setattr(cls, f'_{cls.__name__}__repr_level', next)

    @property
    def _repr_level(self):
        if not hasattr(self, f'_{self.__class__.__name__}__repr_level'):
            setattr(self, f'_{self.__class__.__name__}__repr_level', 0)
        current = getattr(self.__class__, f'_{cls.__class__.__name__}__repr_level')
        nargs = len(self.repr_arg_order)
        next = (current + 1) % nargs
        self.__class__.repr_args = self.repr_arg_order[next]
        print(self.__name__, 'will now repr with', self.repr_args)
        setattr(self.__class__, f'_{self.__class__.__name__}__repr_level', next)


    @property
    def _repr_include_args(self):
        first_done = False
        firsts = getattr(self.__class__, f'_{self.__class__.__name__}__firsts')
        for arg in self.__class__.repr_args:  # always use class repr args
            if not hasattr(self, arg) or getattr(self, arg) is None:  # allow repr of uninitialized classes
                continue
            is_arg = False
            if not first_done:
                if arg in firsts:
                    first_done = True
                    is_arg = True
            yield arg, is_arg

        if hasattr(self, 'unverified') and self.unverified:
            yield 'unverified', False

    @property
    def _repr_base(self):
        pref = self.__class__.__name__ + '('
        suf = ')'
        return pref + ', '.join(('{' + f'{kwarg}' + '}'
                                 if is_arg else
                                 f'{kwarg}={{' + f'{kwarg}' + '}')
                                for kwarg, is_arg in self._repr_include_args) + suf

    @property
    def _repr_args(self):
        return {kwarg:repr(getattr(self, kwarg)) for kwarg, p in self._repr_include_args}

    def _no__str__(self):  # don't use this -- we need sane serialization as the iri
        id_ = self.curie if hasattr(self, 'curie') else super().__repr__()
        return f"{self.__class__.__name__}('{id_}')"

    def __repr__(self):
        return self._repr_base.format(**self._repr_args)


class OntTerm(OntId):
    # TODO need a nice way to pass in the ontology query interface to the class at run time to enable dynamic repr if all information did not come back at the same time
    repr_arg_order = (('curie', 'label', 'synonyms', 'definition'),
                      ('curie', 'label', 'synonyms'),
                      ('curie', 'label'),
                      ('label',),
                      ('curie',),
                      ('curie', 'label', 'definition', 'iri'),
                      ('iri', 'label', 'definition', 'curie'),
                      ('iri', 'label', 'definition'),)

    _cache = {}

    @staticmethod
    def query(*args, **kwargs):
        print(red.format('WARNING:'), 'no query provided to OntTerm')
        # FIXME deal with args
        return QueryResult(query_args=kwargs)

    __firsts = 'curie', 'iri'
    def __new__(cls, curie_or_iri=None,  # cuire_or_iri first to allow creation without keyword
                label=None,
                term=None,
                search=None,
                unverified=None,
                query=None,
                **kwargs):
        kwargs['upstream'] = cls  # FIXME not a good way to do this
        kwargs['curie_or_iri'] = curie_or_iri
        kwargs['label'] = label
        kwargs['term'] = term
        kwargs['search'] = search
        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            cls.__repr_level = 0
            if not hasattr(cls, 'repr_args'):
                cls.repr_args = cls.repr_arg_order[0]

        # FIXME not clear if we really want to do this because it can let
        # unverified terms creep in...
        fail = False
        if curie_or_iri is None and 'curie' not in kwargs and 'iri' not in kwargs and 'suffix' not in kwargs:
            fail = True
            nargs = cullNone(**kwargs)
            if query is not None:
                result = query(**nargs)
            else:
                result = cls.query(**nargs)

            kwargs.update(result)
        else:
            result = None

        self = super().__new__(cls, **kwargs)

        if self.iri in cls._cache:  # FIXME __cache
            return cls._cache[self.iri]
        else:
            cls._cache[self.iri] = self

        self.kwargs = kwargs
        if query is not None:
            self.query = query

        if result is None:
            result = self.query(iri=self, upstream=cls)

        if result:
            for keyword, value in result.items():
                # TODO open vs closed world
                if unverified and keyword in kwargs and kwargs[keyword] != value:
                    raise ValueError(f'Unverified value {keyword}=\'{kwargs[keyword]}\' '
                                     'does not match ontology value {value} for {results["iri"]}')
                #print(keyword, value)
                if keyword not in ('iri', 'curie'):  # already managed by OntId
                    setattr(self, keyword, value)  # TODO value lists...
            self.unverified = False
        else:
            self.unverified = True
            for keyword in set(keyword
                               for keywords in self.repr_arg_order
                               for keyword in keywords
                               if keyword not in cls.__firsts):
                if keyword in kwargs:
                    value = kwargs[keyword]
                else:
                    value = None
                setattr(self, keyword, value)

            print(red.format('WARNING:'), repr(self), '\n')

        if fail:
            print(red.format(repr(self)))
            raise ValueError(f'Your term does not have a valid identifier.\nPlease replace it with {self!r}')

        return self

    # use properties to query for various things to repr

    def __call__(self, *predicates, depth=1):
        qr = self.query(iri=self, predicates=predicates, depth=depth)
        return qr.predicates

    def __repr__(self):  # TODO fun times here
        return super().__repr__()


class OntComplete(OntTerm):
    """ EXPERIMENTAL OntTerm that populates properties from OntQuery """

    class _fakeQuery:
        def __call__(self, *args, **kwargs):
            raise NotImplementedError('Set OntComplete.query = OntQuery(...)')

        @property
        def predicates(self):
            raise NotImplementedError('Set OntComplete.query = OntQuery(...)')

    query = _fakeQuery()

    def __new__(cls, *args, **kwargs):
        for predicate in cls.query.predicates:
            p = OntId(predicate)
            name = p.suffix if p.suffix else p.prefix  # partOf:

            def _prop(self, *predicates, depth=1):
                return cls.__call__(self, *predicates, depth=depth)

            prop = property(_prop)
            setattr(cls, name, prop)

        return super().__new__(*args, **kwargs)


class OntQuery:
    def __init__(self, *services, prefix=None, category=None, upstream=OntTerm):  # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config
        self.services = services
        self.upstream = upstream

    @property
    def predicates(self):
        unique_predicates = set()
        for service in self.services:
            for predicate in service.predicates:
                unique_predicates.add(predicate)

        yield from sorted(unique_predicates)

    def __iter__(self):  # make it easier to init filtered queries
        yield from self.services

    def __call__(self,
                 term=None,           # put this first so that the happy path query('brain') can be used, matches synonyms
                 prefix=None,         # limit search within this prefix
                 category=None,       # like prefix but works on predefined categories of things like 'anatomical entity' or 'species'
                 label=None,          # exact matches only
                 abbrev=None,         # alternately `abbr` as you have
                 search=None,         # hits a lucene index, not very high quality
                 suffix=None,         # suffix is 1234567 in PREFIX:1234567
                 curie=None,          # if you are querying you can probably just use OntTerm directly and it will error when it tries to look up
                 iri=None,            # the most important one
                 predicates=tuple(),  # provided with an iri or a curie to extract more specific triple information
                 depth=1,
                 limit=10,
                 upstream=None,  # FIXME this is NOT a happy way to do this
                ):
        qualifiers = cullNone(prefix=prefix,
                              category=category)
        queries = cullNone(abbrev=abbrev,
                           label=label,
                           term=term,
                           search=search)
        graph_queries = cullNone(predicates=(OntId(p) for p in predicates),
                                 depth=depth)
        identifiers = cullNone(suffix=suffix,
                               curie=curie,
                               iri=iri)
        control = dict(limit=limit)
        if queries and identifiers:
            print(f'\x1b[91mWARNING: An identifier ({list(identifiers)}) was supplied. Ignoring other query parameters {list(queries)}.\x1b[0m')
            queries = {}
        if 'suffix' in identifiers and 'prefix' not in qualifiers:
            raise ValueError('Queries using suffix= must also include an explicit prefix.')
        if len(queries) > 1:
            raise ValueError('Queries only accept a single non-qualifier argument. Qualifiers are prefix=, category=.')
        # TODO more conditions here...

        # TODO? this is one place we could normalize queries as well instead of having
        # to do it for every single OntService
        kwargs = {**qualifiers, **queries, **graph_queries, **identifiers, **control}
        out = []
        for service in self.services:
            if not service.started:
                service.setup()
                service.upstream = self.upstream
            # TODO query keyword precedence if there is more than one
            #print(red.format(str(kwargs)))
            for result in service.query(**kwargs):
                #print(red.format('AAAAAAAAAA'), result)
                out.append(result)

        # do not use these funcs to set the return values, only the error messages
        if upstream is not None:
            def func(result): return upstream(**result)
        elif self.upstream is not None:
            def func(result): return self.upstream(**result)
        else:
            func = lambda r: r

        if len(out) > 1:
            terms = '\n\n'.join(repr(func(result)) for result in out)
            message = f'Query {kwargs} returned more than one result. Please review.\n\n' + terms
            if upstream is not None:
                raise ValueError(message)
            else:
                print(message)
        elif len(out) == 1:
            return out[0]
        else:
            message = f'Query {kwargs} returned no results. Please change your query.'
            if upstream is not None:
                raise ValueError(message)
            else:
                print(message)


class OntService:
    """ Base class for ontology wrappers that define setup, dispatch, query,
        add ontology, and list ontologies methods for a given type of endpoint. """

    def __init__(self):
        self._onts = []
        self.started = False

    def add(self, iri):  # TODO implement with setter/appender?
        self._onts.append(iri)
        raise NotImplementedError()

    @property
    def onts(self):
        yield from self._onts

    @property
    def predicates(self):
        raise NotImplementedError()

    def setup(self):
        self.started = True
        return self

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
        yield 'Queries should return an iterable'
        raise NotImplementedError()


# helpers
class Graph():
    """ I can be pickled! And I can be loaded from a pickle dumped from a graph loaded via rdflib. """
    def __init__(self, triples=tuple()):
        self.store = triples

    def add(triple):
        self.store += triple

    def subjects(self, predicate, object):  # this method by iteself is sufficient to build a keyword based query interface via query(predicate='object')
        for s, p, o in self.store:
            if (predicate is None or predicate == p) and (object == None or object == o):
                yield s

    def predicates(self, subject, object):
        for s, p, o in self.store:
            if (subject is None or subject == s) and (object == None or object == o):
                yield p

    def predicate_objects(subject):  # this is sufficient to let OntTerm work as desired
        for s, p, o in self.store:
            if subject == None or subject == s:
                yield p, o


# services
class BasicService(OntService):
    """ A very simple services for local use only """
    graph = Graph()
    predicate_mapping = {'label':'http://www.w3.org/2000/01/rdf-schema#label'}  # more... from OntQuery.__call__ and can have more than one...

    @property
    def predicates(self):
        yield from sorted(set(self.graph.predicates(None, None)))

    def add(self, triples):
        for triple in triples:
            self.graph.add(triple)

    def setup(self):  # inherit this as `class BasicLocalOntService(ontquery.BasicOntService): pass` and load the default graph during setup
        pass

    def query(self, iri=None, label=None, term=None, search=None):  # right now we only support exact matches to labels
        if iri is not None:
            yield from self.graph.predicate_objects(iri)
        else:
            for keyword, object in kwargs.items():
                predicate = self.predicate_mapping(keyword)
                yield from self.graph.subjects(predicate, object)

        # Dispatching as describe previously is dispatch on type where the type is the set of query
        # features supported by a given OntService. The dispatch method can be dropped from OntQuery
        # and managed with python TypeErrors on kwarg mismatches to the service `query` method
        # like the one implemented here.

from pyontutils import scigraph_client
class SciGraphRemote(OntService):  # incomplete and not configureable yet
    cache = True
    verbose = False
    upstream = OntTerm
    known_inverses = ('partOf:', 'hasPart:'),
    def __init__(self, api_key=None, apiEndpoint='https://scicrunch.org/api/1/scigraph'):
        self.basePath = apiEndpoint
        self.api_key = api_key
        self.inverses = {OntId(k):OntId(v)
                         for _k, _v in self.known_inverses
                         for k, v in ((_k, _v), (_v, _k))}
        super().__init__()

    def add(self, iri):  # TODO implement with setter/appender?
        raise TypeError('Cannot add ontology to remote service.')

    @property
    def predicates(self):
        yield from self._predicates

    def setup(self):
        # TODO make it possible to set these properties dynamically
        # one way is just to do scigraph = SciGraphRemote \\ OntQuery(scigraph)
        self.sgv = scigraph_client.Vocabulary(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.sgg = scigraph_client.Graph(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.sgc = scigraph_client.Cypher(cache=self.cache, verbose=self.verbose, key=self.api_key)
        self.curies = self.sgc.getCuries()  # TODO can be used to provide curies...
        self.categories = self.sgv.getCategories()
        self._predicates = sorted(set(self.sgg.getRelationships()))
        self._onts = self.sgg.getEdges('owl:Ontology')  # TODO incomplete and not sure if this works...
        super().setup()

    def _graphQuery(self, subject, predicate, depth=1, inverse=False):
        # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
        # TODO how to handle depth? this is not an obvious or friendly way to do this
        if predicate.prefix in ('owl', 'rdfs'):
            p = predicate.suffix
        else:
            p = predicate
        d_nodes_edges = self.sgg.getNeighbors(subject, relationshipType=p, depth=depth)  # TODO
        if d_nodes_edges:
            edges = d_nodes_edges['edges']
        else:
            if inverse:
                predicate = self.inverses[predicate]
            print(f'{subject.curie} has no edges with predicate {predicate.curie} ')
            raise StopIteration
        s, o = 'sub', 'obj'
        if inverse:
            s, o = o, s
        if depth > 1:
            subjects = set(subject.curie)
            for e in edges:
                # FIXME need to actually get the transitive closure, this doesn't actually work
                #if e[s] in subjects:
                    #subjects.add(object.curie)
                object = e[o]
                yield object
                continue  # FIXME TODO this is _very_ inefficient for multiple lookups...
                u = self.upstream(object)
                print(repr(u))
                yield u
        else:
            #objects = (self.upstream(e[o]) for e in edges if e[s] == subject.curie)  # TODO efficiency
            objects = (e[o] for e in edges if e[s] == subject.curie)
            yield from objects

    def query(self, iri=None, curie=None,
              label=None, term=None, search=None, abbrev=None,  # FIXME abbrev -> any?
              prefix=None, category=None,
              predicates=tuple(), depth=1,
              limit=10):
        # use explicit keyword arguments to dispatch on type
        if prefix is not None and prefix not in self.curies:
            raise ValueError(f'{prefix} not in {self.__class__.__name__}.prefixes')
        if category is not None and category not in self.categories:
            raise ValueError(f'{category} not in {self.__class__.__name__}.categories')

        qualifiers = cullNone(prefix=prefix, category=category, limit=limit)
        identifiers = cullNone(iri=iri, curie=curie)
        predicates = tuple(OntId(p) for p in predicates)
        if identifiers:
            identifier = OntId(next(iter(identifiers.values())))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # this does not accept qualifiers
            if result is None:
                yield result
                raise StopIteration

            if predicates:  # TODO incoming/outgoing
                for predicate in predicates:
                    values = tuple(sorted(self._graphQuery(identifier, predicate, depth=depth)))
                    result[predicate] = values
                    if predicate in self.inverses:
                        p = self.inverses[predicate]
                        values = tuple(sorted(self._graphQuery(identifier, p, depth=depth, inverse=True)))
                        result[predicate] += values

            results = result,
        elif term:
            results = self.sgv.findByTerm(term, searchSynonyms=True, **qualifiers)
        elif label:
            results = self.sgv.findByTerm(label, searchSynonyms=False, **qualifiers)
        elif search:
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
        for result in results:
            if result['deprecated'] and not identifiers:
                continue
            ni = lambda i: next(iter(i)) if i else None
            predicate_results = {OntId(predicate).curie:result[predicate] for predicate in predicates}
            qr = QueryResult(query_args={**qualifiers, **identifiers, predicates:predicates},
                             iri=result['iri'],
                             curie=result['curie'] if 'curie' in result else result['iri'],  # FIXME...
                             label=ni(result['labels']),
                             definition=ni(result['definitions']),
                             synonyms=result['synonyms'],
                             acronym=result['acronyms'],
                             abbrev=result['abbreviations'],
                             prefix=result['curie'].split(':')[0] if 'curie' in result else None,
                             category=ni(result['categories']),
                             predicates=predicate_results,
                             upstream=self.upstream)
            yield qr


class InterLexRemote(OntService):  # note to self
    pass


class rdflibLocal(OntService):  # reccomended for local default implementation
    #graph = rdflib.Graph()  # TODO pull this out into ../plugins? package as ontquery-plugins?
    # if loading if the default set of ontologies is too slow, it is possible to
    # dump loaded graphs to a pickle gzip and distribute that with a release...

    def add(self, iri, format):
        pass

    def setup(self):
        pass  # graph added at class level

    def dispatch(self, prefix=None, category=None):  # return True if the filters pass
        # TODO
        raise NotImplementedError()

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
        # TODO
        pass


def main():
    import os
    from IPython import embed
    from pyontutils.core import get_api_key, PREFIXES as uPREFIXES
    curies = OntCuries(uPREFIXES)
    #print(curies)
    query = OntQuery(SciGraphRemote(api_key=get_api_key()))
    OntTerm.query = query

    # direct use of query instead of via OntTerm, users should never have to do this
    qr = query(label='brain', prefix='UBERON')
    t = qr.asTerm()  # creation of a term using QueryResult.asTerm
    t1 = OntTerm(**qr)  # creation of a term by passing a QueryResult instance to OntTerm as a dictionary

    # predicates query
    pqr = query(iri='UBERON:0000955', predicates=('hasPart:',))
    pt = pqr.asTerm()
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
