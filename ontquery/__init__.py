class OntCurie:
    def __init__(self, prefix, namespace):
        pass


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

    def dispatch(self, prefix=None, category=None):  # return True if the filters pass
        raise NotImplementedError()

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
        raise NotImplementedError()
        pass


class SciGraphRemote(OntService):  # incomplete and not configureable yet
    def add(self, iri):  # TODO implement with setter/appender?
        raise TypeError('Cannot add ontology to Remote')

    def setup(self):
        self.sgv = scigraph_client.Vocabulary()
        self.sgg = scigraph_client.Graph()
        self.sgc = scigraph_client.Cyper()
        self.curies = sgc.getCuries()  # TODO can be used to provide curies...
        self.categories = sgv.getCategories()
        self._onts = self.sgg.getEdges(relationType='owl:Ontology')  # TODO incomplete and not sure if this works...

    def dispatch(self, prefix=None, category=None):  # return True if the filters pass
        # FIXME? alternately all must be true instead of any being true?
        if prefix is not None and prefix in self.curies:
            return True
        if categories is not None and prefix in self.categories:
            return True
        return False

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
        # TODO
        pass


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


class OntQuery:
    def __init__(self, *services, prefix=None, category=None):  # services from OntServices
        # check to make sure that prefix valid for ontologies
        # more config
        self.services = services

    def __iter__(self):  # make it easier to init filtered queries
        yield from self.services

    def __call__(self,
                 term=None,      # put this first so that the happy path query('brain') can be used, matches synonyms
                 prefix=None,    # limit search within this prefix
                 category=None,  # like prefix but works on predefined categories of things like 'anatomical entity' or 'species'
                 label=None,     # exact matches only
                 abbrev=None,    # alternately `abbr` as you have
                 search=None,    # hits a lucene index, not very high quality
                 id=None,        # alternatly `local_id` to clarify that 
                 curie=None,     # if you are querying you can probably just use OntTerm directly and it will error when it tries to look up
                 limit=10):
        kwargs = dict(term=term,
                      prefix=prefix,
                      category=category,
                      label=label,
                      abbrev=abbrev,
                      search=search,
                      id=id,
                      curie=curie)
        # TODO? this is one place we could normalize queries as well instead of having
        # to do it for every single OntService
        out = []
        for service in self.onts:
            if service.dispatch(prefix=prefix, category=category):
                # TODO query keyword precedence if there is more than one
                for result in service.query(**kwawrgs):
                    out.append(OntTerm(query=service.query, **result))
        if len(out) > 1:
            for term in out:
                print(term)
            raise ValueError('More than one result')
        else:
            return out[0]


class OntID(str):  # superclass is a suggestion
    def __init__(self, curie_or_iri=None, prefix=None, suffix=None, curie=None, iri=None, **kwargs):
       # logic to construct iri or expand from curie to iri or just be an iri
       super().__init__(iri)


class OntTerm(OntID):
    # TODO need a nice way to pass in the ontology query interface to the class at run time to enable dynamic repr if all information did not come back at the same time
    def __init__(self, query=None, **kwargs):  # curie=None, prefix=None, id=None
       self.kwargs = kwargs
       if query is not None:
           self.query = query
       super().__init__(**kwargs)

    # use properties to query for various things to repr

    @property
    def subClassOf(self):
       return self.query(self.curie, 'subClassOf')  # TODO

    def __repr__(self):  # TODO fun times here
       pass


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


