"""
Implementation of the query interface that provides a layer of separation between
identifiers and lookup services for finding and validating them.
"""

from ontquery import plugin, exceptions as exc
from ontquery.utils import mimicArgs, cullNone, one_or_many, log


class OntQuery:
    def __init__(self, *services, prefix=tuple(), category=tuple(), instrumented=None):
        # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config

        self._prefix = one_or_many(prefix)
        self._category = one_or_many(category)

        _services = [] 
        for maybe_service in services:
            if isinstance(maybe_service, str):
                service = plugin.get(service)
            else:
                service = maybe_service

            _services.append(service)

        self._services = tuple(_services)
        if instrumented:
            self._instrumented = instrumented
            self._OntId = self._instrumented._uninstrumented_class()

        else:
            raise TypeError('instrumented is a required keyword argument')

    def add(self, *services):
        """ add low priority services """
        # FIXME dupes
        self._services += services

    def ladd(self, *services):
        """ add high priority services """
        # FIXME dupes
        self._services = services + self._services

    def radd(self, *services):
        """ add low priority services """
        # FIXME dupes
        self._services = self._services + services

    def setup(self):
        for service in self.services:
            if not service.started:
                service.setup(instrumented=self._instrumented)

        # NOTE if you add a service after the first use of a query
        # you will have to call setup manually, which is reaonsable
        # if you are adding a service in that way ...

        self.__call__ = self._rcall__
        self._predicates = self._predicates_r

    @property
    def predicates(self):
        return self._predicates()

    def _predicates(self):
        self.setup()
        return self.predicates

    def _predicates_r(self):
        unique_predicates = set()
        for service in self.services:
            for predicate in service.predicates:
                unique_predicates.add(predicate)

        return tuple(sorted(unique_predicates))  # this needs to be returned as thing of known size not a generator

    @property
    def services(self):
        return self._services

    # see if we can get away with using ladd
    #@services.setter
    #def services(self, value):
        #""" sometimes we need to reorder services """
        #self._services = value

    def __iter__(self):  # make it easier to init filtered queries
        yield from self.services

    def __call__(self, *args, **kwargs):
        """ first time only call """
        self.setup()
        return self.__call__(*args, **kwargs)

    def _rcall__(self,
                 term=None,           # put this first so that the happy path query('brain') can be used, matches synonyms
                 prefix=tuple(),      # limit search within these prefixes
                 category=None,       # like prefix but works on predefined categories of things like 'anatomical entity' or 'species'
                 label=None,          # exact matches only
                 abbrev=None,         # alternately `abbr` as you have
                 search=None,         # hits a lucene index, not very high quality
                 suffix=None,         # suffix is 1234567 in PREFIX:1234567
                 curie=None,          # if you are querying you can probably just use OntTerm directly and it will error when it tries to look up
                 iri=None,            # the most important one
                 predicates=tuple(),  # provided with an iri or a curie to extract more specific triple information
                 exclude_prefix=tuple(),
                 depth=1,
                 direction='OUTGOING',
                 limit=10,
                 include_deprecated=False,
                 include_supers=False,
                 include_all_services=False,
                 raw=False,
    ):
        prefix = one_or_many(prefix) + self._prefix
        category = one_or_many(category) + self._category
        qualifiers = cullNone(prefix=prefix if prefix else None,
                              exclude_prefix=exclude_prefix if exclude_prefix else None,
                              category=category if category else None)
        queries = cullNone(abbrev=abbrev,
                           label=label,
                           term=term,
                           search=search)
        graph_queries = cullNone(predicates=tuple(self._OntId(p) if ':' in p else
                                                  p for p in predicates),  # size must be known no generator
                                 depth=depth,
                                 direction=direction)
        identifiers = cullNone(suffix=suffix,
                               curie=curie,
                               iri=iri)
        control = dict(include_deprecated=include_deprecated,
                       include_supers=include_supers,
                       limit=limit)
        if queries and identifiers:
            log.warning(f'\x1b[91mWARNING: An identifier ({list(identifiers)}) was supplied. Ignoring other query parameters {list(queries)}.\x1b[0m')
            queries = {}
        if 'suffix' in identifiers and 'prefix' not in qualifiers:
            raise ValueError('Queries using suffix= must also include an explicit prefix.')
        if len(queries) > 1:
            raise ValueError('Queries only accept a single non-qualifier argument. '
                             'Qualifiers are prefix=, category=.')
        # TODO more conditions here...

        # TODO? this is one place we could normalize queries as well instead of having
        # to do it for every single OntService
        kwargs = {**qualifiers, **queries, **graph_queries, **identifiers, **control}
        for j, service in enumerate(self.services):
            # TODO query keyword precedence if there is more than one
            #print(red.format(str(kwargs)))
            # TODO don't pass empty kwargs to services that can't handle them?
            for i, result in enumerate(service.query(**kwargs)):
                #print(red.format('AAAAAAAAAA'), result)
                if result:
                    yield result if raw else result.asTerm()
                    if search is None and term is None and result.label and not include_all_services:
                        return  # FIXME order services based on which you want first for now, will work on merging later


class OntQueryCli(OntQuery):
    raw = False  # return raw QueryResults

    def __init__(self, *services, prefix=tuple(), category=tuple(), query=None,
                 instrumented=None):
        if query is not None:
            if services:
                raise ValueError('*services and query= are mutually exclusive arguments, '
                                 'please remove one')

            self._prefix = query._prefix
            self._category = query._category
            self._services = query.services
            self._instrumented = query._instrumented
            self._OntId = query._OntId

        else:
            super().__init__(*services, prefix=prefix, category=category,
                             instrumented=instrumented)

    @mimicArgs(OntQuery.__call__)
    def __call__(self, *args, **kwargs):
        gen = super().__call__(*args, **kwargs)
        if 'raw' in kwargs and kwargs['raw']:
            return list(gen)
        else:
            return [term for term in gen if True or term.set_next_repr('curie', 'label')]

    def _old_call_rest(self):
        """ oof """
        i = None
        for i, result in enumerate(super().__call__(*args, **kwargs)):
            if i > 0:
                if i == 1:
                    log.info(f'\n{func(old_result)!r}\n')

                log.info(f'\n{func(result)!r}\n')
                continue
            if i == 0:
                old_result = result

        if i is None:
            log.error(f'\nCliQuery {args} {kwargs} returned no results. Please change your query.\n')

        elif i > 0:
            log.error(f'\nCliQuery {args} {kwargs} returned more than one result. Please review.\n')

        else:
            return func(result)
