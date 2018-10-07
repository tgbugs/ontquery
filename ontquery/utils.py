from functools import wraps

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
