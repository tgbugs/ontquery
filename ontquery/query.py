"""
Implementation of the query interface that provides a layer of separation between
identifiers and lookup services for finding and validating them.
"""

from ontquery import plugin, exceptions as exc
from ontquery.utils import mimicArgs, cullNone
from ontquery.terms import OntId  # FIXME doen't want to import OntId ...


class OntQuery:
    def __init__(self, *services, prefix=None, category=None):  # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config
        _services = [] 
        for maybe_service in services:
            if isinstance(maybe_service, str):
                service = plugin.get(service)
            else:
                service = maybe_service

            _services.append(service)

        self._services = tuple(_services)

    def add(self, *services):
        self._services += services

    @property
    def predicates(self):
        unique_predicates = set()
        for service in self.services:
            if not service.started:
                service.setup()
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
    ):
        qualifiers = cullNone(prefix=prefix,
                              category=category)
        queries = cullNone(abbrev=abbrev,
                           label=label,
                           term=term,
                           search=search)
        graph_queries = cullNone(predicates=tuple(OntId(p) if ':' in p else
                                                  p for p in predicates),  # size must be known no generator
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
                    if search is None and term is None and result.label:
                        return  # FIXME order services based on which you want first for now, will work on merging later


class OntQueryCli(OntQuery):
    raw = False  # return raw QueryResults

    def __init__(self, *services, prefix=None, category=None, query=None):
        if query is not None:
            if services:
                raise ValueError('*services and query= are mutually exclusive arguments, '
                                 'please remove one')

            self._services = query.services
        else:
            self._services = services

    @mimicArgs(OntQuery.__call__)
    def __call__(self, *args, **kwargs):
        def func(result):
            if result.hasOntTerm and not self.raw:
                t = result.OntTerm
                t.set_next_repr('curie', 'label')
                return t
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
            print(f'\nCliQuery {args} {kwargs} returned no results. Please change your query.\n')
        elif i > 0:
            print(f'\nCliQuery {args} {kwargs} returned more than one result. Please review.\n')
        else:
            return func(result)


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
        if self.iri is None:
            raise exc.ShouldNotHappenError(f'I can\'t believe you\'ve done this! {self!r}')
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
