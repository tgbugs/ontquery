from .utils import Graph, QueryResult


class OntService:
    """ Base class for ontology wrappers that define setup, dispatch, query,
        add ontology, and list ontologies methods for a given type of endpoint. """

    def __init__(self):
        if not hasattr(self, '_onts'):
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

    def setup(self, instrumented=None, **kwargs):
        if instrumented is None:
            raise TypeError('instrumented is a required argument!')  # FIXME only require instrumented

        self.OntId = instrumented._uninstrumented_class()
        self.OntTerm = instrumented
        self.QueryResult = QueryResult.new_from_instrumented(instrumented)

        self.started = True
        return self

    def query(self, *args, **kwargs):  # needs to conform to the OntQuery __call__ signature
        yield 'Queries should return an iterable'
        raise NotImplementedError()


class BasicService(OntService):
    """ A very simple service for local use only """
    graph = Graph()
    predicate_mapping = {'label': 'http://www.w3.org/2000/01/rdf-schema#label',
                         'term': 'http://www.w3.org/2000/01/rdf-schema#label'}
    # more... from OntQuery.__call__ and can have more than one...

    @property
    def predicates(self):
        yield from sorted(set(self.graph.predicates(None, None)))

    def add(self, triples):
        for triple in triples:
            self.graph.add(triple)

    def setup(self, **kwargs):
        # inherit this as `class BasicLocalOntService(ontquery.BasicOntService): pass` and load the default graph during setup
        super().setup(**kwargs)

    def query(self, iri=None, label=None, term=None, search=None):
        # right now we only support exact matches to labels
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
