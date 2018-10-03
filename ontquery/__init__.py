from functools import wraps
from collections import UserDict
from six import text_type
from inspect import signature
from urllib import parse

red = '\x1b[31m{}\x1b[0m'

def cullNone(**kwargs):
    return {k:v for k, v in kwargs.items() if v is not None}


def mimicArgs(function_to_mimic):
    def decorator(function):
        @wraps(function_to_mimic)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)
        return wrapper
    return decorator


class dictclass(type):
    def __setitem__(self, key, value):
        if key not in self._dict:
            self._dict[key] = value
        elif self._dict[key] == value:
            pass
        else:
            raise KeyError(f'{key} already set to {self._dict[key]}')

    def __getitem__(self, key):
        return self._dict[key]


class QueryResult:
    """ Encapsulate query results and allow for clear and clean documentation
        of how a particular service maps their result terminology onto the
        ontquery keyword api. """

    class _OntTerm_:
        def __new__(cls, *args, **kwargs):
            raise TypeError('ontutils.QueryResult._OntTerm has not been set!')

    _OntTerm = _OntTerm_

    def __init__(self,
                 query_args,
                 iri=None,
                 curie=None,
                 label=None,
                 labels=tuple(),
                 abbrev=None,  # TODO
                 acronym=None,  # TODO
                 definition=None,
                 synonyms=tuple(),
                 deprecated=None,
                 prefix=None,
                 category=None,
                 predicates=None,  # FIXME dict
                 _graph=None,
                 source=None,
    ):
        self.__query_args = query_args  # for debug
        self.__dict = {}
        for k, v in dict(iri=iri,
                         curie=curie,
                         label=label,
                         labels=labels,
                         definition=definition,
                         synonyms=synonyms,
                         deprecated=deprecated,
                         predicates=predicates,
                         _graph=_graph,
                         source=source).items():
            # this must return the empty values for all keys
            # so that users don't have to worry about hasattring
            # to make sure they aren't about to step into a typeless void

            setattr(self, k, v)
            self.__dict[k] = v
            #self.__dict__[k] = v

    @property
    def OntTerm(self):  # FIXME naming
        return self._OntTerm(iri=self.iri)  # TODO works best with a cache

    @property
    def hasOntTerm(self):  # FIXME naming
        # run against _OntTerm to prevent recursion
        if self._OntTerm == self._OntTerm_:
            return False
        else:
            return True

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


class OntCuries(metaclass=dictclass):
    """ A bad implementation of a singleton dictionary based namespace.
        Probably better to use metaclass= to init this so types can be tracked.
    """
    # TODO how to set an OntCuries as the default...
    def __new__(cls, *args, **kwargs):
        #if not hasattr(cls, '_' + cls.__name__ + '_dict'):
        if not hasattr(cls, '_dict'):
            cls._dict = {}
        cls._dict.update(dict(*args, **kwargs))
        return cls._dict

    @classmethod
    def qname(cls, iri):
        # sort in reverse to match longest matching namespace first TODO/FIXME trie
        for prefix, namespace in sorted(cls._dict.items(), key=lambda kv: len(kv[1]), reverse=True):
            if iri.startswith(namespace):
                suffix = iri[len(namespace):]
                return ':'.join((prefix, suffix))
        return iri


class OntId(text_type):  # TODO all terms singletons to prevent nastyness
    _namespaces = OntCuries  # overwrite when subclassing to switch curies...
    repr_arg_order = (('curie',),
                      ('prefix', 'suffix'),
                      ('iri',))
    __firsts = 'curie', 'iri'  # FIXME bad for subclassing __repr__ behavior :/
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
        # FIXME these assignments prevent updates when OntCuries changes
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
    def repr_level(cls, verbose=True):  # FIXME naming
        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            setattr(cls, f'_{cls.__name__}__repr_level', 0)
            #cls.__repr_level = 0 # how is this different....
        current = getattr(cls, f'_{cls.__name__}__repr_level')
        nargs = len(cls.repr_arg_order)
        next = (current + 1) % nargs
        cls.repr_args = cls.repr_arg_order[next]
        if verbose:
            print(cls.__name__, 'will now repr with', cls.repr_args)
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

        if hasattr(self, 'validated') and not self.validated:
            yield 'validated', False

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

    class _Query:
        services = tuple()
        def __call__(self, *args, **kwargs):
            print(red.format('\nWARNING:'), 'no query provided to ontquery.OntTerm\n')
            return
            yield

    query = _Query()

    __firsts = 'curie', 'iri'
    def __new__(cls, curie_or_iri=None,  # cuire_or_iri first to allow creation without keyword
                label=None,
                term=None,
                search=None,
                validated=None,
                query=None,
                **kwargs):
        kwargs['curie_or_iri'] = curie_or_iri
        kwargs['label'] = label
        kwargs['term'] = term
        kwargs['search'] = search
        kwargs['validated'] = validated
        kwargs['query'] = query
        if curie_or_iri and 'labels' in kwargs:
            raise ValueError('labels= is not a valid keyword for results not returned by a query')
        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            cls.__repr_level = 0
            if not hasattr(cls, 'repr_args'):
                cls.repr_args = cls.repr_arg_order[0]

        orig_kwargs = {k:v for k, v in kwargs.items()}

        noId = False
        if curie_or_iri is None and 'curie' not in kwargs and 'iri' not in kwargs and 'suffix' not in kwargs:
            noId = True
            nargs = cullNone(**kwargs)
            if query is not None:
                results_gen = query(**nargs)
            else:
                results_gen = cls.query(**nargs)

            results_gen = tuple(results_gen)
            if results_gen:
                if len(results_gen) <= 1:
                    kwargs.update(results_gen[0])
        else:
            results_gen = None

        try:
            self = super().__new__(cls, **kwargs)
        except StopIteration:  # no iri found
            self = text_type.__new__(cls, '')  # issue will be dealt with downstream

        self.orig_kwargs = orig_kwargs
        self.kwargs = kwargs

        if query is not None:
            self.query = query

        if hasattr(self.query, 'raw') and not self.query.raw:
            raise TypeError(f'{self.query} result not set to raw, avoiding infinite recursion.')

        if self.iri not in cls._cache or not validated or 'predicates' in kwargs:  # FIXME __cache
            # FIXME if results_gen returns > 1 result this goes infinite
            self.__real_init__(validated, results_gen, noId)
            cls._cache[self.iri] = self

        return cls._cache[self.iri]

    def __init__(self, *args, **kwargs):
        """ do nothing """

    def __real_init__(self, validated, results_gen, noId):
        """ If we use __init__ here it has to accept args that we don't want. """

        if results_gen is None:
            extra_kwargs = {}
            if 'predicates' in self.kwargs:
                extra_kwargs['predicates'] = self.kwargs['predicates']
            # can't gurantee that all endpoints work on the expanded iri
            results_gen = self.query(iri=self.iri, curie=self.curie, **extra_kwargs)
        
        i = None
        for i, result in enumerate(results_gen):
            if i > 0:
                if i == 1:
                    pass
                    print(repr(TermRepr(**old_result)), '\n')
                print(repr(TermRepr(**result)), '\n')
                continue
            if i == 0:
                old_result = result

            for keyword, value in result.items():
                # TODO open vs closed world
                orig_value = self.orig_kwargs.get(keyword, None)
                if orig_value is not None and orig_value != value:
                    if keyword == 'label' and orig_value in result['labels']:
                        pass
                    elif keyword == 'predicates':
                        pass  # query will not match result
                    else:
                        self.__class__.repr_args = 'curie', keyword
                        if validated == False:
                            raise ValueError(f'Unvalidated value {keyword}={orig_value!r} '
                                             f'does not match {self.__class__(**result)!r}')
                        else:
                            raise ValueError(f'value {keyword}={orig_value!r} '
                                             f'does not match {self.__class__(**result)!r}')

                #print(keyword, value)
                if keyword not in self.__firsts:  # already managed by OntId
                    setattr(self, keyword, value)  # TODO value lists...
            self.validated = True

        if i is None:
            self.validated = False
            for keyword in set(keyword  # FIXME repr_arg_order should not be what is setting this?!?!
                                for keywords in self.repr_arg_order
                                for keyword in keywords
                                if keyword not in self.__firsts):
                if keyword in self.orig_kwargs:
                    value = self.orig_kwargs[keyword]
                else:
                    value = None
                setattr(self, keyword, value)

            print(red.format('WARNING:'), repr(self), '\n')
            for service in self.query.services:
                self.termRequests = []
                if hasattr(service, 'termRequest'):
                    makeRequest = service.termRequest(self)
                    termRequests.append(makeRequest)
        elif i > 0:
            raise ValueError(f'\nQuery {self.orig_kwargs} returned more than one result. Please review.\n')
        elif noId:
            #print(red.format(repr(self)))
            raise ValueError(f'Your term does not have a valid identifier.\nPlease replace it with {self!r}')

    def __call__(self, predicate, *predicates, depth=1, direction='OUTGOING'):
        predicates = (predicate,) + predicates  # ensure at least one
        results_gen = self.query(iri=self, predicates=predicates, depth=depth, direction=direction)
        out = {}
        for result in results_gen:  # FIXME should only be one?!
            for k, v in result.predicates.items():
                out[k] = v  # FIXME last one wins?!?!
        self.predicates.update(out)  # FIXME klobbering issues
        return out

    def __repr__(self):  # TODO fun times here
        return super().__repr__()


class TermRepr(OntTerm):
    repr_arg_order = (('curie', 'label', 'synonyms'),)
    __firsts = 'curie', 'iri'

    def __new__(cls, *args, **kwargs):
        iri = kwargs['iri']
        self = str.__new__(cls, iri)
        return self

    def __init__(self, *args, **kwargs):
        self.iri = kwargs['iri']
        self.curie = kwargs['curie']
        self.label = kwargs['label']

    @property
    def curie(self):
        return self._curie

    @curie.setter
    def curie(self, value):
        self._curie = value

    @property
    def iri(self):
        return self._iri

    @iri.setter
    def iri(self, value):
        self._iri = value


TermRepr.repr_level(verbose=False)


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
    def __init__(self, *services, prefix=None, category=None):  # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config
        self._services = services

    def add(self, *services):
        self._services += services

    @property
    def predicates(self):
        unique_predicates = set()
        for service in self.services:
            for predicate in service.predicates:
                unique_predicates.add(predicate)

        return tuple(sorted(unique_predicates))  # this needs to be returned as thing of known size not a generator

    @property
    def services(self):
        return self._services

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
                 direction='OUTGOING',
                 limit=10,
                 wut=[0]
    ):
        qualifiers = cullNone(prefix=prefix,
                              category=category)
        queries = cullNone(abbrev=abbrev,
                           label=label,
                           term=term,
                           search=search)
        graph_queries = cullNone(predicates=tuple(OntId(p) for p in predicates),  # size must be known no generator
                                 depth=depth,
                                 direction=direction)
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
        for j, service in enumerate(self.services):
            if not service.started:
                service.setup()
            # TODO query keyword precedence if there is more than one
            #print(red.format(str(kwargs)))
            # TODO don't pass empty kwargs to services that can't handle them?
            for i, result in enumerate(service.query(**kwargs)):
                #print(red.format('AAAAAAAAAA'), result)
                if result:
                    yield result
                    return  # FIXME order services based on which you want first for now, will work on merging later


class OntQueryCli(OntQuery):
    raw = False  # return raw QueryResults

    def __init__(self, *services, prefix=None, category=None, query=None):
        if query is not None:
            if services:
                raise ValueError('*services and query= are mutually exclusive arguments, please remove one')

            self._services = query.services
        else:
            self._services = services

    @mimicArgs(OntQuery.__call__)
    def __call__(self, *args, **kwargs):
        def func(result):
            if result.hasOntTerm and not self.raw:
                return result.OntTerm
            else:
                return result

        i = None
        for i, result in enumerate(super().__call__(*args, **kwargs)):
            if i > 0:
                if i == 1:
                    print(f'\n{func(old_result)!r}\n')
                print(f'\n{func(result)!r}\n')
                continue
            if i == 0:
                old_result = result

        if i is None:
            print(f'\nQuery {kwargs} returned no results. Please change your query.\n')
        elif i > 0:
            print(f'\nQuery {kwargs} returned more than one result. Please review.\n')
        else:
            return func(result)


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
                predicate = self.predicate_mapping[keyword]
                yield from self.graph.subjects(predicate, object)  # FIXME bad result structure

        # Dispatching as describe previously is dispatch on type where the type is the set of query
        # features supported by a given OntService. The dispatch method can be dropped from OntQuery
        # and managed with python TypeErrors on kwarg mismatches to the service `query` method
        # like the one implemented here.

from pyontutils import scigraph
class SciGraphRemote(OntService):  # incomplete and not configureable yet
    cache = True
    verbose = False
    known_inverses = ('', ''),
    def __init__(self, api_key=None, apiEndpoint=None, OntId=OntId):  # apiEndpoint=None -> default from pyontutils.devconfig
        self.basePath = apiEndpoint
        self.api_key = api_key
        self.OntId = OntId
        self.inverses = {self.OntId(k):self.OntId(v)
                         for _k, _v in self.known_inverses
                         for k, v in ((_k, _v), (_v, _k))
                         if _k and _v}
        super().__init__()

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
        self.categories = self.sgv.getCategories()
        self._predicates = sorted(set(self.sgg.getRelationships()))
        self._onts = self.sgg.getEdges('owl:Ontology')  # TODO incomplete and not sure if this works...
        super().setup()

    def _graphQuery(self, subject, predicate, depth=1, direction='OUTGOING', inverse=False):
        # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
        # TODO how to handle depth? this is not an obvious or friendly way to do this
        if predicate.prefix in ('owl', 'rdfs'):
            p = predicate.suffix
        else:
            p = predicate
        d_nodes_edges = self.sgg.getNeighbors(subject, relationshipType=p, depth=depth, direction=direction)  # TODO
        if d_nodes_edges:
            edges = d_nodes_edges['edges']
        else:
            if inverse:
                predicate = self.inverses[predicate]
            print(f'{subject.curie} has no edges with predicate {predicate.curie} ')
            return
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
                # to make OntTerm(object) work we need to be able to use the 'meta' section...
                yield object # FIXME TODO this is _very_ inefficient for multiple lookups...
        else:
            objects = (e[o] for e in edges if e[s] == subject.curie)  # TODO OntTerm(e[0])
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

        qualifiers = cullNone(prefix=prefix, category=category, limit=limit)
        identifiers = cullNone(iri=iri, curie=curie)
        predicates = tuple(self.OntId(p) for p in predicates)
        if identifiers:
            identifier = self.OntId(next(iter(identifiers.values())))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # this does not accept qualifiers
            if result is None:
                return

            if predicates:  # TODO incoming/outgoing
                for predicate in predicates:
                    values = tuple(sorted(self._graphQuery(identifier, predicate, depth=depth, direction=direction)))
                    result[predicate] = values
                    if predicate in self.inverses:
                        p = self.inverses[predicate]
                        values = tuple(sorted(self._graphQuery(identifier, p, depth=depth, direction=direction, inverse=True)))
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
            ni = lambda i: next(iter(sorted(i))) if i else None  # FIXME multiple labels issue
            predicate_results = {predicate.curie:result[predicate] for predicate in predicates}  # FIXME hasheqv on OntId
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


import requests
class SciCrunchRemote(SciGraphRemote):
    known_inverses = ('partOf:', 'hasPart:'),
    defaultEndpoint = 'https://scicrunch.org/api/1/scigraph'
    def __init__(self, api_key=None, apiEndpoint=defaultEndpoint, OntId=OntId):
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
    host = 'localhost'
    port = '8505'
    def __init__(self, *args, **kwargs):
        import rdflib  # FIXME
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

    def query(self, iri=None, curie=None, label=None, predicates=None, **_):
        def get(url, headers={'Content-Type':'text/turtle'}):
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

        if curie:
            if curie.startswith('ILX:') and iri:
                # FIXME hack, can replace once the new resolver is up
                url = iri.replace('uri.interlex.org', f'{self.host}:{self.port}')
            else:
                url = f'http://{self.host}:{self.port}/base/curies/{curie}?local=True'
        elif label:
            url = f'http://{self.host}:{self.port}/base/lexical/{label}'
        else:
            return None

        resp = get(url)
        if not resp.ok:
            return None
        ttl = resp.content
        g = self.Graph().parse(data=ttl, format='turtle')
        ia_iri = isAbout(g)

        rdll = rdflibLocal(g)
        maybe_out = list(rdll.query(curie=curie, label=label, predicates=predicates))  # TODO cases where ilx is preferred will be troublesome
        if maybe_out:
            yield from maybe_out
        else:
            yield from rdll.query(iri=ia_iri, label=label, predicates=predicates)


class rdflibLocal(OntService):  # reccomended for local default implementation
    #graph = rdflib.Graph()  # TODO pull this out into ../plugins? package as ontquery-plugins?
    # if loading if the default set of ontologies is too slow, it is possible to
    # dump loaded graphs to a pickle gzip and distribute that with a release...

    def __init__(self, graph, OntId=OntId):
        self.OntId = OntId
        import rdflib
        from pyontutils.core import NIFRID
        self.NIFRID = NIFRID
        self.rdflib = rdflib
        self.graph = graph
        self.predicate_mapping = {'label':rdflib.RDFS.label,}
        super().__init__()

    def add(self, iri, format):
        pass

    def setup(self):
        # graph is already set up...
        super().setup()

    @property
    def predicates(self):
        yield from sorted(set(self.graph.predicates()))

    def query(self, iri=None, curie=None, label=None, predicates=None, **kwargs):
        # right now we only support exact matches to labels FIXME
        kwargs['curie'] = curie
        kwargs['iri'] = iri
        kwargs['label'] = label
        #kwargs['term'] = term
        #kwargs['search'] = search
        #supported = sorted(QueryResult(kwargs))
        if iri is not None or curie is not None:
            out = {'predicates':{}}
            identifier = self.OntId(curie=curie, iri=iri)
            gen = self.graph.predicate_objects(self.rdflib.URIRef(identifier))
            out['curie'] = identifier.curie
            out['iri'] = identifier.iri
            translate = {self.rdflib.RDFS.label:'label',
                         #self.rdflib.RDFS.subClassOf:'subClassOf',
                         #self.rdflib.RDF.type:'type',
                         #self.rdflib.OWL.disjointWith:'disjointWith',
                         #self.NIFRID.definingCitation:'definingCitation',
                        }
            o = None
            for p, o in gen:
                pn = translate.get(p, None)
                if isinstance(o, self.rdflib.Literal):
                    o = o.toPython()
                if pn is None:
                    # TODO translation and support for query result structure
                    # FIXME lists instead of klobbering results with mulitple predicates
                    if isinstance(o, self.rdflib.URIRef):
                        o = self.OntId(o)  # FIXME we we try to use OntTerm directly everything breaks
                        # FIXME these OntIds also do not derive from rdflib... sigh
                    out['predicates'][self.OntId(p).curie] = o  # curie to be consistent with OntTerm behavior
                    #print(red.format('WARNING:'), 'untranslated predicate', p)
                else:
                    out[pn] = o

            if o is not None:
                yield QueryResult(kwargs, **out, _graph=self.graph, source=self)  # if you yield here you have to yield from below
        else:
            for keyword, object in kwargs.items():
                if keyword in self.predicate_mapping:
                    predicate = self.predicate_mapping[keyword]
                    gen = self.graph.subjects(predicate, self.rdflib.Literal(object))
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
