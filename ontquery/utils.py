import logging
from functools import wraps

red = '\x1b[31m{}\x1b[0m'


def makeSimpleLogger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    ch = logging.StreamHandler()  # FileHander goes to disk
    fmt = ('[%(asctime)s] - %(levelname)8s - '
           '%(name)14s - '
           '%(filename)16s:%(lineno)-4d - '
           '%(message)s')
    formatter = logging.Formatter(fmt)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


log = makeSimpleLogger('ontquery')


__logged = set()
def _already_logged(thing):
    case = thing in __logged
    if not case:
        __logged.add(thing)

    return case


def subclasses(start, done=None):
    if done is None:
        done = set()
    for sc in start.__subclasses__():
        if sc is not None and sc not in done:
            done.add(sc)
            yield sc
            yield from subclasses(sc, done)


class SubClassCompare:
    def __init__(self, cls):
        self.cls = cls

    def __lt__(self, other, *, forgt=False):
        if self.cls is None:  # i.e. None is the least derived class
            return False
        elif other.cls is None:
            return True
        elif issubclass(other.cls, self.cls):
            # if you are a subclass of the other, you are greater
            # fewer parent classes rank lower
            return True
        elif issubclass(self.cls, other.cls):
            return False
        else:
            # NOTE useful in some cases
            # but not useful in the case where you just want
            # the parent class to be above the child but not
            # above other classes
            ls, lo = len(self.cls.mro()), len(other.cls.mro())
            return ls < lo

    def __gt__(self, other):
        lt = self.__lt__(other, forgt=True)
        return not lt
        #return False if lt is None else not lt

    def __eq__(self, other):
        return self.cls is other.cls or not self < other and not self > other

    def __repr__(self):
        return f'SubClassCompare({self.cls!r})'


def bunch(pairs):
    """ pairs -> dict """
    out = {}
    for k, v in pairs:
        if k not in out:
            out[k] = []

        out[k].append(v)

    return out


def cullNone(**kwargs):
    return {k:v for k, v in kwargs.items() if v is not None}


def one_or_many(arg):
    return tuple() if not arg else ((arg,)
                                    if isinstance(arg, str)
                                    else arg)

def mimicArgs(function_to_mimic):
    def decorator(function):
        @wraps(function_to_mimic)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)
        return wrapper
    return decorator


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


class QueryResult:
    """ Encapsulate query results and allow for clear and clean documentation
        of how a particular service maps their result terminology onto the
        ontquery keyword api. """

    @classmethod
    def new_from_instrumented(cls, instrumented):
        return type(cls.__name__, (cls,), dict(_instrumented=instrumented))

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
                 type=None,
                 types=tuple(),
                 _graph=None,
                 _blob=None,  # FIXME unify graph/blob under progenitor ?
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
                         type=type,
                         types=types,
                         _graph=_graph,
                         _blob=_blob,
                         source=source).items():
            # this must return the empty values for all keys
            # so that users don't have to worry about hasattring
            # to make sure they aren't about to step into a typeless void

            setattr(self, k, v)
            self.__dict[k] = v
            #self.__dict__[k] = v

    @property
    def OntTerm(self):  # FIXME naming XXXX deprecate this
        if self.iri is None:
            raise BaseException(f'I can\'t believe you\'ve done this! {self!r}')
        return self._instrumented._from_query_result(self)

    def asTerm(self):
        return self.OntTerm

    @property
    def hasOntTerm(self):  # FIXME naming
        # run against _OntTerm to prevent recursion
        return hasattr(self, '_instrumented')

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
        return f'{self.__class__.__name__}({self.__dict!r})'
