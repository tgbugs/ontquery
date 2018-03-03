from collections import UserDict
from six import text_type
from inspect import signature

def cullNone(**kwargs):
    return {k:v for k, v in kwargs.items() if v is not None}

class QueryResult:
    """ Encapsulate query results and allow for clear and clean documentation
        of how a particular service maps their result terminology onto the
        ontquery keyword api. """
    def __init__(self,
                 iri=None,
                 curie=None,
                 label=None,
                 abbrev=None,  # TODO
                 acronym=None,  # TODO
                 definition=None,
                 synonyms=None,
                 subClassOf=None,
                 prefix=None,
                 category=None,):
        for k, v in cullNone(iri=iri,
                             curie=curie,
                             label=label,
                             definition=definition,
                             synonyms=synonyms,
                             subClassOf=subClassOf).items():
            self.__dict__[k] = v

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        raise ValueError('Cannot set results of a query.')


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
        #_kwargs = dict(curie_or_iri=curie_or_iri,
                       #prefix=prefix,
                       #suffix=suffix,
                       #curie=curie,
                       #iri=iri)
        cls.__repr_level = 0

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
                prefix, suffix = curie_ci.split(':')
                iri_ci = cls._make_iri(prefix, suffix)

        if curie is not None:
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
            raise KeyError(f'Unknown curie prefix: {prefix}.')

    @classmethod
    def repr_level(cls):  # FIXME naming
        current = getattr(cls, f'_{cls.__name__}__repr_level')
        nargs = len(cls.repr_arg_order)
        next = (current + 1) % nargs
        print(cls.__name__, 'will now repr with', cls.repr_arg_order[next])
        setattr(cls, f'_{cls.__name__}__repr_level', next)

    @property
    def _repr_include_args(self):
        first_done = False
        firsts = getattr(self.__class__, f'_{self.__class__.__name__}__firsts')
        for arg in self.repr_arg_order[getattr(self.__class__, f'_{self.__class__.__name__}__repr_level')]:
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

    def __repr__(self):
        return self._repr_base.format(**self._repr_args)


class OntTerm(OntId):
    # TODO need a nice way to pass in the ontology query interface to the class at run time to enable dynamic repr if all information did not come back at the same time
    repr_arg_order = (('curie', 'label', 'definition'),
                      ('curie', 'label'),
                      ('label',),
                      ('curie',),
                      ('curie', 'label', 'definition', 'iri'),
                      ('iri', 'label', 'definition', 'curie'),
                      ('iri', 'label', 'definition'),)

    @staticmethod
    def query(*args, **kwargs): return tuple()

    __firsts = 'curie', 'iri'
    def __new__(cls, curie_or_iri=None,  # cuire_or_iri first to allow creation without keyword
                label=None,
                term=None,
                search=None,
                unverified=None, query=None, **kwargs):
        kwargs['curie_or_iri'] = curie_or_iri
        kwargs['label'] = label
        cls.__repr_level = 0
        self = super().__new__(cls, **kwargs)
        self.kwargs = kwargs
        if query is not None:
            self.query = query

        result = self.query(iri=self)
        if result:
            for keyword, value in result.items():
                # TODO open vs closed world
                if unverified and keyword in kwargs and kwargs[keyword] != value:
                    raise ValueError(f'Unverified value {keyword}=\'{kwargs[keyword]}\' '
                                     'does not match ontology value {value} for {results["iri"]}')
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
        return self

    # use properties to query for various things to repr

    @property
    def subClassOf(self):
       return self.query(self.curie, 'subClassOf')  # TODO

    def __repr__(self):  # TODO fun times here
        return super().__repr__()


class OntQuery:
    def __init__(self, *services, prefix=None, category=None):  # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config
        self.services = services

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
                 limit=10):
        qualifiers = cullNone(prefix=prefix,
                              category=category)
        queries = cullNone(abbrev=abbrev,
                           label=label,
                           term=term,
                           search=search)
        identifiers = cullNone(suffix=suffix,
                               curie=curie,
                               iri=iri)
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
        kwargs = {**qualifiers, **queries, **identifiers}
        out = []
        for service in self.services:
            # TODO query keyword precedence if there is more than one
            print(kwargs)
            for result in service.query(**kwargs):
                out.append(OntTerm(results['iri']))  # FIXME
                #out.append(OntTerm(query=service.query, **result))
        if len(out) > 1:
            for term in out:
                print(term)
            raise ValueError('Query returned more than one result. Please review.')
        else:
            return out[0]


class OntService:
    """ Base class for ontology wrappers that define setup, dispatch, query,
        add ontology, and list ontologies methods for a given type of endpoint. """
    def __init__(self):
        self._onts = []
        self.setup()

    def add(self, iri):  # TODO implement with setter/appender?
        self._onts.append(iri)
        raise NotImplementedError()

    @property
    def onts(self):
        yield from self._onts

    def setup(self):
        raise NotImplementedError()

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
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
    
    def predicate_objects(subject):  # this is sufficient to let OntTerm work as desired
        for s, p, o in self.store:
            if subject == None or subject == s:
                yield p, o


# services
class BasicService(OntService):
    """ A very simple services for local use only """
    graph = Graph()
    predicate_mapping = {'label':'http://www.w3.org/2000/01/rdf-schema#label'}  # more... from OntQuery.__call__ and can have more than one...
    def add(self, triples):
        for triple in triples:
            self.graph.add(triple)

    def setup(self):  # inherit this as `class BasicLocalOntService(ontquery.BasicOntService): pass` and load the default graph during setup
        pass

    def query(self, iri=None, label=None):  # right now we only support exact matches to labels
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
    def add(self, iri):  # TODO implement with setter/appender?
        raise TypeError('Cannot add ontology to remote service.')

    def setup(self):
        self.sgv = scigraph_client.Vocabulary(cache=self.cache)
        self.sgg = scigraph_client.Graph(cache=self.cache)
        self.sgc = scigraph_client.Cypher(cache=self.cache)
        self.curies = self.sgc.getCuries()  # TODO can be used to provide curies...
        self.categories = self.sgv.getCategories()
        self._onts = self.sgg.getEdges('owl:Ontology')  # TODO incomplete and not sure if this works...

    def query(self, iri=None, curie=None, label=None, term=None, search=None, prefix=None, category=None, predicates=tuple()):
        # use explicit keyword arguments to dispatch on type
        if prefix is not None and prefix not in self.curies:
            raise ValueError(f'{prefix} not in {self.__class__.__name__}.prefixes')
        if category is not None and category not in self.categories:
            raise ValueError(f'{category} not in {self.__class__.__name__}.categories')
        quanlifiers = cullNone(prefix=prefix, category=category)

        identifiers = cullNone(iri=iri, curie=curie)
        if identifiers:
            identifier = next(iter(identifiers.values()))  # WARNING: only takes the first if there is more than one...
            result = self.sgv.findById(identifier)  # in theory could pass qualifiers here, but seems like it could be abused
            if predicates:  # TODO incoming/outgoing
                for predicate in predicates:
                    # TODO need predicate mapping... also subClassOf inverse?? hasSubClass??
                    d_nodes_edges = sgg.getNeighbors(identifier, relationshipType=predicate, depth=1)  # TODO
        elif term:
            result = sgv.findByTerm(term, searchSynonyms=True)
        elif label:
            result = sgv.findByTerm(term, searchSynonyms=False)
        elif search:
            result = sgv.searchByTerm(term)
        else:
            raise ValueError('No query prarmeters provided!')

        # TODO deprecated handling

        # TODO transform result to expected
        print(result)
        ni = lambda i: next(iter(i)) if i else None
        qr = QueryResult(iri=result['iri'],
                         curie=result['curie'],
                         label=ni(result['labels']),
                         definition=ni(result['definitions']),
                         synonyms=result['synonyms'],
                         acronym=result['acronyms'],
                         abbrev=result['abbreviations'],
                         prefix=result['curie'].split(':')[0],
                         category=ni(result['categories']),


                         )
        return qr


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
    pass
from IPython import embed
from pyontutils.core import PREFIXES as uPREFIXES
curies = OntCuries(uPREFIXES)
#print(curies)
query = OntQuery(SciGraphRemote())
OntTerm.query = query
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
