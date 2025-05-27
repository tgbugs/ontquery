import sys
import copy
from itertools import chain
from urllib.parse import quote
from . import exceptions as exc, trie
from .utils import cullNone, subclasses, log, SubClassCompare, _already_logged
from .query import OntQuery

# FIXME ipython notebook?
# this still seems wrong, I want to know not how the file is running
# but whether the code being invoked when we call OntTerm has been
# saved to disk
interactive = getattr(sys, 'ps1', sys.flags.interactive)


class dictclass(type):

    def values(self):
        return self._dict.values()

    def __setitem__(self, key, value):
        if key not in self._dict:
            self._dict[key] = value
        elif self._dict[key] == value:
            pass
        else:
            raise KeyError(f'{key} already set to {self._dict[key]}')

    def __iter__(self):
        return iter(self._dict)

    def __getitem__(self, key):
        return self._dict[key]


class OntCuries(metaclass=dictclass):
    """ A bad implementation of a singleton dictionary based namespace.
        Probably better to use metaclass= to init this so types can be tracked.
    """
    # TODO how to set an OntCuries as the default...
    def __new__(cls, *args, **kwargs):
        #if not hasattr(cls, '_' + cls.__name__ + '_dict'):
        if not hasattr(cls, '_dict'):
            cls._dict = {}
            cls._n_to_p = {}
            cls._strie = {}
            cls._trie = {}

        for p, namespace in dict(*args, **kwargs).items():
            sn = str(namespace)
            trie.insert_trie(cls._trie, sn)
            cls._dict[p] = sn
            cls._n_to_p[sn] = p

        if args or kwargs:
            cls._pn = sorted(cls._dict.items(), key=lambda kv: len(kv[1]), reverse=True)

        return cls._dict

    @classmethod
    def reset(cls):
        delattr(cls, '_dict')

    @classmethod
    def new(cls):
        # FIXME yet another pattern that I don't like :/
        clsdict = dict(_dict={},
                       _n_to_p={},
                       _strie={},
                       _trie={},)

        return type('OntCuries', (OntCuries,), clsdict)  # FIXME this does not subclass propertly even when using cls ... :/

    @classmethod
    def populate(cls, graph):
        """ populate an rdflib graph with these curies """
        [graph.bind(k, v) for k, v in cls._dict.items()]

    @classmethod
    def identifier_prefixes(cls, curie_iri_prefix):
        return [cls._n_to_p[n] for n in cls.identifier_namespaces(curie_iri_prefix)]

    @classmethod
    def identifier_namespaces(cls, curie_iri_prefix):
        if ':' not in curie_iri_prefix:
            iri = cls._dict[curie_iri_prefix]
        elif '://' in curie_iri_prefix:
            iri = curie_iri_prefix
        else:
            iri = cls._dict[curie_iri_prefix.split(':', 1)[0]]

        return list(trie.get_namespaces(cls._trie, iri))

    @classmethod
    def qname(cls, iri):
        # while / is not *technically* allowed in prefix names by ttl
        # RDFa and JSON-LD do allow it, so we are going to allow it too
        # TODO cache the output mapping?
        try:
            namespace, suffix = trie.split_uri(iri)
            if namespace.endswith('://'):
                raise ValueError(f'Bad namespace {namespace}')
        except ValueError as e:
            try:
                namespace = str(iri)
                prefix = cls._n_to_p[namespace]
                return prefix + ':'
            except KeyError as e:
                return iri  # can't split it then we're in trouble probably

        if namespace not in cls._strie:
            trie.insert_strie(cls._strie, cls._trie, namespace)

        if cls._strie[namespace]:
            pl_namespace = trie.get_longest_namespace(cls._strie[namespace], iri)
            if pl_namespace is not None:
                namespace = pl_namespace
                suffix = iri[len(namespace):]

        try:
            prefix = cls._n_to_p[namespace]
            return ':'.join((prefix, suffix))
        except KeyError:
            new_iri = namespace[:-1]
            sep = namespace[-1]
            qname = cls.qname(new_iri)
            # this works because when we get to an unsplitable case we simply fail
            # caching can help with performance here because common prefixes that
            # have not been shortened will show up in the cache
            return qname + sep + suffix

    @classmethod
    def _qname_old(cls, iri):
        # sort in reverse to match longest matching namespace first TODO/FIXME trie
        for prefix, namespace in cls._pn:
            if iri.startswith(namespace):
                suffix = iri[len(namespace):]
                return ':'.join((prefix, suffix))
        return iri


class Id:
    """ base for all identifiers, both local and global """

    def normalize(self):
        # the sane flow for nearly every identifier system is
        # id -> normalize -> instrument -> resolve -> retrieve meta/data
        # we leave out the explicit retrieve
        raise NotImplementedError


class LocalId(Id):
    """ Local identifier without the context to globalize it
        It is usually ok to skip using this class and just
        use a python string or integer (that is converted to a string)
    """


class Identifier(Id):
    """ any global identifier, manages the local/global transition """

    def __hash__(self):
        return hash((self.__class__, super().__hash__()))

    def __eq__(self, other):
        def complex_type_compare(a, b):
            # if both are instrumed, or both are not instrumed
            # then proceed to compare
            aii = isinstance(a, InstrumentedIdentifier)
            bii = isinstance(b, InstrumentedIdentifier)
            return aii and bii or (not aii and not bii)  # (not (xor aii bii))

        if type(self) == type(other) or complex_type_compare(self, other):
            return str(self) == str(other)

        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def query_init(cls, *services, query_class=None, **kwargs):
        if query_class is None:
            query_class = OntQuery

        if not getattr(query_class, 'raw', True):
            raise TypeError('FIXME TODO only raw query classes can be used here '
                            'for non-raw initialize them directly so they won\'t bind '
                            'as the query for the instrumented form. This thing needs '
                            'a complete revamp along the lines of pathlib so that an '
                            'instrumented class can be initialized from the side')

        instrumented = cls._instrumented_class()
        cls.query = query_class(*services, instrumented=instrumented, **kwargs)
        return cls.query

    @classmethod
    def _instrumented_class(cls):
        if issubclass(cls, InstrumentedIdentifier): 
            return cls

        elif issubclass(cls, Identifier):
            # when initing from an uninstrumented id the last
            # instrumented subclass prior to the next uninstrumented
            # subclass will be used, so if I subclass OntId to create
            # OrcId (an identifier for residents of Mordor) and also
            # subclass to create OntTerm, and then OrcRecord, OntId
            # will pick OntTerm when instrumenting rather than OrcRecord

            candidate = None
            for sc in subclasses(cls):#sorted(subclasses(cls), key=SubClassCompare):
                if (issubclass(sc, InstrumentedIdentifier) and
                    not sc.skip_for_instrumentation
                    # note that this will trigger the creation of additional interveneing
                    # classes, I don't really see a way around this
                    and sc._uninstrumented_class() is cls):
                    candidate = sc
                elif issubclass(sc, Identifier):
                    break

            if candidate is None:
                raise TypeError(f'{cls} has no direct subclasses that are Instrumented')

            return candidate

        else:
            raise TypeError(f'Don\'t know what to do with a {type(cls)}')

    @classmethod
    def _uninstrumented_class(cls):
        # FIXME walking back down the hierarchy there can be another instrumented
        # class that appears first, if this happens (because we didn't explicilty)
        # subclass the uninstrumented class, then we need to construct a new one
        # there may be side effects here, but I think they are probably worth the risk
        # for everything to work as desired, we hvae
        if issubclass(cls, InstrumentedIdentifier): 
            has_intervening_instrumented = False
            for candidate in sorted(cls.mro(), key=SubClassCompare, reverse=True):
                if (issubclass(candidate, Identifier) and not
                    issubclass(candidate, InstrumentedIdentifier)):
                    if has_intervening_instrumented and candidate not in cls.__bases__:
                        log.warning(f'{cls} has intervening instrumented classes '
                                 f'between it and its uninstrumented form {candidate}')
                        @classmethod
                        def instcf(cls, _instc=cls):
                            return _instc

                        candidate = type(candidate.__name__ + '_for_' + cls.__name__,
                                         (candidate,),
                                         dict(_instrumented_class=instcf))

                        @classmethod
                        def uinstcf(cls, _uinstc=candidate):
                            return _uinstc

                        cls.__bases__ += (candidate,)
                        # XXX WARNING this is a static change
                        cls._uninstrumented_class = uinstcf

                    return candidate
                elif (issubclass(candidate, InstrumentedIdentifier) and
                      candidate is not InstrumentedIdentifier and
                      # InstrumentedIdentifier never actually intervenes
                      # and if included will cause a TypeError above when we add candidate to bases
                      candidate is not cls):
                    has_intervening_instrumented = True

            raise TypeError(f'{cls} has no parent that is Uninstrumented')

        elif issubclass(cls, Identifier):
            return cls

        else:
            raise TypeError(f'Don\'t know what to do with a {type(cls)}')

    def asInstrumented(self):
        inst_class = self._instrumented_class()
        return inst_class(self)

    def asUninstrumented(self):
        uninst_class = self._uninstrumented_class()
        return uninst_class(self)


class InstrumentedIdentifier(Identifier):
    """ classes that instrument a type of identifier to make it actionable """

    skip_for_instrumentation = False


class OntId(Identifier, str):  # TODO all terms singletons to prevent nastyness
    _namespaces = OntCuries  # overwrite when subclassing to switch curies...
    _valid_repr_args = ('curie', 'iri', 'prefix', 'suffix')
    repr_arg_order = (('curie',),
                      ('prefix', 'suffix'),
                      ('iri',))
    _firsts = 'curie', 'iri'  # FIXME bad for subclassing __repr__ behavior :/
    class Error(Exception): pass
    class BadCurieError(Error): pass
    class UnknownPrefixError(Error): pass

    def __new__(cls, curie_or_iri=None, prefix=None, suffix=None, curie=None,
                iri=None, **kwargs):

        if type(curie_or_iri) == cls:
            return curie_or_iri
        elif isinstance(curie_or_iri, cls):
            return cls(str(curie_or_iri))

        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            cls.__repr_level = 0
            cls._oneshot_old_repr_args = None
            if not hasattr(cls, 'repr_args'):
                cls.repr_args = cls.repr_arg_order[0]

        iri_ps, iri_ci, iri_c = None, None, None

        if prefix is not None and suffix is not None:
            #curie_ps = ':'.join(prefix, suffix)
            iri_ps = cls._make_iri(prefix, suffix)

        if curie_or_iri is not None:
            _is_iri = False
            if isinstance(curie_or_iri, OntId):
                # we can't make any assumptions about whether the
                # source context for an OntId subclass carries the
                # same local convetions, so we normalize to iri here
                curie_or_iri = curie_or_iri.iri
                _is_iri = True

            if (_is_iri or
                curie_or_iri.startswith('http://') or
                curie_or_iri.startswith('https://') or
                curie_or_iri.startswith('file://')):
                iri_ci = curie_or_iri
                curie_ci = cls._namespaces.qname(iri_ci)
                if curie_ci != iri_ci:  # FIXME this is bad ... figure out where qname returning None is an issue ...
                    prefix, suffix = curie_ci.split(':', 1)
                else:
                    prefix, suffix = None, None
            else:
                curie_ci = curie_or_iri
                try:
                    prefix, suffix = curie_ci.split(':', 1)
                except ValueError as e:
                    raise cls.BadCurieError(f'Could not split curie {curie_ci!r} '
                                            'is it actually an identifier?') from e
                iri_ci = cls._make_iri(prefix, suffix)

        if curie is not None and curie != iri:
            prefix, suffix = curie.split(':', 1)
            iri_c = cls._make_iri(prefix, suffix)

        if isinstance(iri, OntId):
            # we can't assume anything about the context that
            # an OntId carries with it, so we convert here
            iri = iri.iri

        iris = iri_ps, iri_ci, iri_c, iri
        unique_iris = set(i for i in iris if i is not None)

        if len(unique_iris) > 1:
            breakpoint()
            raise ValueError(f'All ways of constructing iris not match! {sorted(unique_iris)}')
        else:
            try:
                iri = next(iter(unique_iris))
            except StopIteration as e:
                raise TypeError('No identifier was provided!') from e

        if iri is not None:
            # normalization step in case there is a longer prefix match
            curie_i = cls._namespaces.qname(iri)
            if curie_i != iri:  # FIXME TODO same issue as above with qname returning None
                prefix_i, suffix_i = curie_i.split(':', 1)
            else:
                prefix_i, suffix_i = None, None

            #if prefix and prefix_i != prefix:
                #print('Curie changed!', prefix + ':' + suffix, '->', curie_i)
            prefix, suffix = prefix_i, suffix_i
            if ((suffix is not None and not suffix.startswith('//') and curie_i == iri)
                or (suffix is None and '://' not in iri and curie_i == iri)):
                raise ValueError(f'You have provided a curie {curie_i} as an iri!')

        if prefix is not None and (' ' in prefix or ' ' in suffix):
            raise cls.BadCurieError(f'{prefix}:{suffix} has an invalid charachter in it!')

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
    def namespace(self):
        if self.prefix:
            return self.namespaces[self.prefix]

    @property
    def iprefix(self):
        """ alias for self.namespace """
        return self.namespace

    @property
    def curie(self):
        if self.prefix or self.suffix:
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
            raise cls.UnknownPrefixError(
                f'Unknown curie prefix: {prefix} for {prefix}:{suffix}')

    @property
    def quoted(self):
        return quote(self.iri, safe=tuple())

    def asTerm(self):
        inst_class = self._instrumented_class()
        return inst_class(self)

    @classmethod
    def set_repr_args(cls, *args):
        bads = [arg for arg in args if arg not in cls._valid_repr_args]
        if bads:
            raise ValueError(f'{bads} are not valid repr args for {cls}')
        else:
            cls.repr_args = args

    @classmethod
    def repr_level(cls, verbose=True):  # FIXMe naming
        if not hasattr(cls, f'_{cls.__name__}__repr_level'):
            setattr(cls, f'_{cls.__name__}__repr_level', 0)
            #cls.__repr_level = 0 # how is this different....
        current = getattr(cls, f'_{cls.__name__}__repr_level')
        nargs = len(cls.repr_arg_order)
        next = (current + 1) % nargs
        cls.repr_args = cls.repr_arg_order[next]
        if verbose:
            log.info(f'{cls.__name__} will now repr with {cls.repr_args}')
        setattr(cls, f'_{cls.__name__}__repr_level', next)

    @classmethod
    def set_next_repr(cls, *repr_args):
        cls._oneshot_old_repr_args = cls.repr_args
        cls.repr_args = repr_args

    @classmethod
    def reset_repr_args(cls):
        if hasattr(cls, '_oneshot_old_repr_args') and cls._oneshot_old_repr_args is not None:
            cls.repr_args = cls._oneshot_old_repr_args
            cls._oneshot_old_repr_args = None

    @property
    def _repr_level(self):
        if not hasattr(self, f'_{self.__class__.__name__}__repr_level'):
            setattr(self, f'_{self.__class__.__name__}__repr_level', 0)
        current = getattr(self.__class__, f'_{cls.__class__.__name__}__repr_level')
        nargs = len(self.repr_arg_order)
        next = (current + 1) % nargs
        self.__class__.repr_args = self.repr_arg_order[next]
        log.info(f'{self.__name__} will now repr with {self.repr_args}')
        setattr(self.__class__, f'_{self.__class__.__name__}__repr_level', next)

    @property
    def _repr_include_args(self):
        first_done = False
        #firsts = getattr(self.__class__, f'_{self.__class__.__name__}__firsts')
        firsts = self._firsts
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
        try:
            rargs = self._repr_args
            if not any(rargs.values()):
                return self.__class__.__name__ + f'({self.iri})'

            out = self._repr_base.format(**rargs)
            return out
        finally:
            self.reset_repr_args()

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls, iri=self.iri)
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls, iri=self.iri)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))
        return result


class OntTerm(InstrumentedIdentifier, OntId):
    # TODO need a nice way to pass in the ontology query interface to the class at run time to enable dynamic repr if all information did not come back at the same time
    _valid_repr_args = OntId._valid_repr_args + ('label', 'synonyms', 'definition')
    repr_arg_order = (('curie', 'label', 'synonyms', 'definition'),
                      ('curie', 'label', 'synonyms'),
                      ('curie', 'label'),
                      ('label',),
                      ('curie',),
                      ('curie', 'label', 'definition', 'iri'),
                      ('iri', 'label', 'definition', 'curie'),
                      ('iri', 'label', 'definition'),)

    _cache = {}

    #__firsts = 'curie', 'iri'

    def __new__(cls, curie_or_iri=None, prefix=None, suffix=None, curie=None,
                iri=None, **kwargs):
        self = super().__new__(cls,
                               curie_or_iri=curie_or_iri,
                               prefix=prefix,
                               suffix=suffix,
                               curie=curie,
                               iri=iri,
                               **kwargs)
        kwargs['iri'] = self.iri
        kwargs['curie'] = self.curie
        self._bind_result(**kwargs)
        return self

    def __init__(self, *args, **kwargs):
        pass

    def _bind_result(self, **kwargs):
        try:
            result = self._get_query_result(**kwargs)
            self._bind_query_result(result, **kwargs)
        except StopIteration:
            self.validated = False
            self.label = None  # the label attr should always be present even on failure

    def _get_query_result(self, **kwargs):
        extra_kwargs = {}
        if 'predicates' in kwargs:
            extra_kwargs['predicates'] = kwargs['predicates']
        # can't gurantee that all endpoints work on the expanded iri
        #log.info(repr(self.asId()))
        results_gen = self.query(iri=self.iri, curie=self.curie, raw=True, **extra_kwargs)
        i = None
        for i, result in enumerate(results_gen):
            if i > 0:
                if result.iri == old_result.iri:
                    i = 0  # if we get the same record from multiple places it is ok
                    if result.curie is None:
                        log.warning(f'No curie for {result.iri} from {result.source}')
                    elif old_result.curie is None:
                        pass  # already warned
                    elif result.curie != old_result.curie:
                        log.warning('curies do not match between services!'
                                    f'{result.curie} != {old_result.curie}')
                else:
                    if i == 1:
                        log.info(repr(old_result.asTerm()))
                        #log.info(repr(TermRepr(**old_result)) + '\n')

                    log.info(repr(result.asTerm()))
                    #log.info(repr(TermRepr(**result)) + '\n')
                    continue

                # TODO merge from multiple goes here?

            if i == 0:
                old_result = result

            if result.label:  # FIXME first label
                return result

        if i is None:
            raise StopIteration
        else:
            skip = ('owl:Thing', 'owl:Class', 'ilxtr:materialEntity',
                    'ilxtr:cell', 'ilxtr:gene')

            if result.curie not in skip:
                # FIXME why are we repeatedly constructing
                # owl:Thing and friends?
                if not _already_logged(result.curie):
                    log.warning('No results have labels! '
                                f'{old_result.asTerm()!r} '
                                f'{result.asTerm()!r}')

            return result

    def _bind_query_result(self, result, **kwargs):
        def validate(keyword, value):
            # TODO open vs closed world
            orig_value = kwargs.get(keyword, None)
            empty_iterable = hasattr(orig_value, '__iter__') and not orig_value
            if ((orig_value is not None and not empty_iterable)
                and value is not None and orig_value != value):
                if str(orig_value) == value:
                    pass  # rdflib.URIRef(a) != Literl(a) != a so we have to convert
                elif (keyword == 'label' and
                      (orig_value in result['labels'] or
                       orig_value.lower() == value.lower())):
                    pass
                elif keyword == 'predicates':
                    pass  # query will not match result
                elif keyword == 'curie':
                    if hasattr(result.source, '_remote_curies'):
                        ov = self._uninstrumented_class()(orig_value)
                        if ov.prefix not in result.source._remote_curies:
                            if not _already_logged((ov.prefix, result.source)):
                                log.info(f'curie prefix {ov.prefix} not in remote curies for {result.source}')

                            return

                    raise ValueError(f'value {keyword}={orig_value!r} '
                                     f'does not match {keyword}={result[keyword]!r}')

                else:
                    self.__class__.repr_args = 'curie', keyword
                    if 'validated' in kwargs and kwargs['validated'] == False:
                        raise ValueError(f'Unvalidated value {keyword}={orig_value!r} '
                                         f'does not match {keyword}={result[keyword]!r}')
                    else:
                        raise ValueError(f'value {keyword}={orig_value!r} '
                                         f'does not match {keyword}={result[keyword]!r}')

            elif orig_value is None and value is None:
                pass

        for keyword, value in result.items():
            validate(keyword, value)
            if keyword not in self._firsts:  # already managed by OntId
                if keyword == 'source':  # FIXME the things i do in the name of documentability >_<
                    keyword = '_source'

                if keyword == 'predicates':
                    value = self._normalize_predicates(value)

                setattr(self, keyword, value)  # TODO value lists...

        self.validated = True
        self._query_result = result

    def _normalize_predicates(self, predicates):
        """ sigh ... too many identifiers in a hierarchy :/ """
        # yay we can remove this by getting rid of uninstrumented
        # identifiers for normal use entirely

        def fix(e):
            if type(e) == type(self):
                return e
            if isinstance(e, InstrumentedIdentifier):
                return self._instrumented_class()(e)
            elif isinstance(e, Identifier):
                return self._uninstrumented_class()(e)
            else:
                return e

        return {k:tuple(fix(e) for e in v) if isinstance(v, tuple) else fix(v)
                for k, v in predicates.items()}

    @classmethod
    def _from_query_result(cls, result):
        self = super().__new__(cls, **result)
        self._bind_query_result(result)
        return self

    def fetch(self, *service_names):  # TODO
        """ immediately fetch the current term """

    def fetch_with(self, query=None):  # TODO
        """ add to a future bulk fetch """
        # depending on the nature of the services for the fetcher
        # and which ones are selected we can optimize to either
        # send a bunch of queries at the same time if the remote
        # side of the service doesn't support what we want, OR
        # we can send a bulk query all at once, dealing with the
        # rankings is a bit of a pain though
        query.add_to_bulk_fetch(self)

    def debug(self):
        """ return debug information """
        if self._graph:
            print(self._graph.serialize(format='nifttl').decode())

    def asPreferred(self):
        """ Return the term attached to its preferred id """
        if not self.validated:
            # FIXME sort of a nullability issue
            return self

        if 'TEMP:preferredId' in self.predicates:
            # NOTE having predicates by default is not supported by all remotes
            term = self.predicates['TEMP:preferredId'][0].asTerm()  # FIXME produces wrong instrumented
        elif self.deprecated:
            rb = self('replacedBy:', asTerm=True)
            if rb:
                term = rb[0]
        else:
            term = self

        if term != self:
            term._original_term = self  # FIXME naming for prov ...

        return term

    def asId(self):
        uninst_class = self._uninstrumented_class()
        return uninst_class(self)

    @property
    def source(self):
        """ The service that the term came from.
            It is not obvious that source is being set from QueryResult.
            I'm sure there are other issues like this due to the strange
            interaction between OntTerm and QueryResult. """

        if hasattr(self, '_source'):
            # TODO consider logging a warning if no _source?
            # and not validated?
            return self._source

    @classmethod
    def search(cls, expression, prefix=None, filters=tuple(), limit=40):
        """ Something that actually sort of works """
        OntTerm = cls
        if expression is None and prefix is not None:
            # FIXME bad convention
            return sorted(qr
                          for qr in OntTerm.query(search=expression,
                                                  prefix=prefix, limit=limit))

        return sorted(set(next(OntTerm.query(term=s)).OntTerm
                          for qr in OntTerm.query(search=expression,
                                                  prefix=prefix, limit=limit)
                          for s in chain(OntTerm(qr.iri).synonyms, (qr.label,))
                          if all(f in s for f in filters)),
                          key=lambda t:t.label)

    def __call__(self, predicate, *predicates, depth=1, direction='OUTGOING',
                 asTerm=False, asPreferred=False, include_supers=False):
        """ Retrieve additional metadata for the current term. If None is provided
            as the first argument the query runs against all predicates defined for
            each service. """
        # FIXME the difference in return type between single_out and multi out is a nightmare
        asTerm = asTerm or asPreferred
        single_out = not predicates and predicate is not None
        if predicate is None:
            predicates = self.query.predicates
        else:
            predicates = (predicate,) + predicates  # ensure at least one

        results_gen = self.query(iri=self, predicates=predicates, depth=depth,  # XXX observe passing OntTerm as iri here
                                 direction=direction, include_supers=include_supers)
        out = {}
        for result in results_gen:  # FIXME should only be one?!
            for k, v in result.predicates.items():
                if not isinstance(v, tuple):
                    v = v,

                if asTerm:
                    v = tuple(self.__class__(v) if not isinstance(v, self.__class__) and isinstance(v, OntId)
                              else v for v in v)
                    if asPreferred:
                        v = tuple(t.asPreferred() if isinstance(t, self.__class__) else t for t in v)

                if k in out:
                    out[k] += v
                else:
                    out[k] = v

        if not hasattr(self, 'predicates'):
            self.predicates = {}

        self.predicates.update(out)  # FIXME klobbering issues

        if single_out:
            if out:
                p = OntId(predicate).curie  # need to normalize here since we don't above
                if p in out:  # FIXME rdflib services promiscuously returns predicates
                    return out[p]

            return tuple()  # more consistent return value so can always iterate
        else:
            return out

    @property
    def type(self):
        if not hasattr(self, '_type'):
            try:
                qr = next(self.query(self.iri))
                self._type = qr.type
                self._types = qr.types
            except StopIteration as e:
                # FIXME this happens when a term is moved
                # from one term type to another and its
                # original source is lost
                log.warning(f'No results for {self.__class__.__name__}('
                            f'{self.iri})')
                self._type = None
                self._types = tuple()

        return self._type

    @type.setter
    def type(self, value):
        self._type = value

    @property
    def types(self):
        if not hasattr(self, '_types'):
            try:
                qr = next(self.query(self.iri))
                self._type = qr.type
                self._types = qr.types
            except StopIteration as e:
                # FIXME this happens when a term is moved
                # from one term type to another and its
                # original source is lost
                log.warning(f'No results for {self.__class__.__name__}('
                            f'{self.iri})')
                self._type = None
                self._types = tuple()

        return self._types

    @types.setter
    def types(self, value):
        self._types = value

    def __repr__(self):  # TODO fun times here
        return super().__repr__()

class _OntTerm(OntTerm):
    """ Old OntTerm implementation """

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
        cls._oneshot_old_repr_args = None  # FIXME why does this fail in the hasattr case? below?!
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
            self = str.__new__(cls, '')  # issue will be dealt with downstream

        self.orig_kwargs = orig_kwargs
        self.kwargs = kwargs

        if query is not None:
            self.query = query

        if hasattr(self.query, 'raw') and not self.query.raw:
            raise TypeError(f'{self.query} result not set to raw, avoiding infinite recursion.')

        if self.iri not in cls._cache or validated == False or 'predicates' in kwargs:  # FIXME __cache
            # FIXME if results_gen returns > 1 result this goes infinite
            self.__real_init__(validated, results_gen, noId)
            # returning without error does NOT imply validated

        return self

    def __init__(self, *args, **kwargs):
        """ do nothing """

    def __real_init__(self, validated, results_gen, noId):
        """ If we use __init__ here it has to accept args that we don't want. """

        if results_gen is None:
            extra_kwargs = {}
            if 'predicates' in self.kwargs:
                extra_kwargs['predicates'] = self.kwargs['predicates']
            # can't gurantee that all endpoints work on the expanded iri
            #print(self.iri, self.kwargs)
            results_gen = self.query(iri=self.iri, curie=self.curie, **extra_kwargs)

        i = None
        for i, result in enumerate(results_gen):
            if i > 0:
                if result.iri == old_result.iri:
                    i = 0  # if we get the same record from multiple places it is ok
                    if result.curie != old_result.curie:
                        pass  # TODO log warning
                else:
                    if i == 1:
                        log.info(repr(TermRepr(**old_result)) + '\n')

                    log.info(repr(TermRepr(**result)) + '\n')
                    continue

            if i == 0:
                old_result = result

            for keyword, value in result.items():
                # TODO open vs closed world
                orig_value = self.orig_kwargs.get(keyword, None)
                empty_iterable = hasattr(orig_value, '__iter__') and not orig_value
                if ((orig_value is not None and not empty_iterable)
                    and value is not None and orig_value != value):
                    if str(orig_value) == value:
                        pass  # rdflib.URIRef(a) != Literl(a) != a so we have to convert
                    elif (keyword == 'label' and
                          (orig_value in result['labels'] or
                           orig_value.lower() == value.lower())):
                        pass
                    elif keyword == 'predicates':
                        pass  # query will not match result
                    else:
                        self.__class__.repr_args = 'curie', keyword
                        if validated == False:
                            raise ValueError(f'Unvalidated value {keyword}={orig_value!r} '
                                             f'does not match {keyword}={result[keyword]!r}')
                        else:
                            raise ValueError(f'value {keyword}={orig_value!r} '
                                             f'does not match {keyword}={result[keyword]!r}')
                elif orig_value is None and value is None:
                    pass
                #elif value is None:  # can't error here, need to continue
                    #raise ValueError(f'Originally given {keyword}={orig_value!r} '
                                     #f'but got {keyword}=None as a result!')
                #elif orig_value is None:  # not an error
                    #raise ValueError()

                #print(keyword, value)
                if keyword not in self._firsts:  # already managed by OntId
                    if keyword == 'source':  # FIXME the things i do in the name of documentability >_<
                        keyword = '_source'

                    setattr(self, keyword, value)  # TODO value lists...
            self.validated = True
            self._query_result = result

        if i is None:
            self._source = None
            self.validated = False
            for keyword in set(keyword  # FIXME repr_arg_order should not be what is setting this?!?!
                               for keywords in self.repr_arg_order
                               for keyword in keywords
                               if keyword not in self._firsts):
                if keyword in self.orig_kwargs:
                    value = self.orig_kwargs[keyword]
                else:
                    value = None
                setattr(self, keyword, value)
            rargs = {k:v for k, v in self.orig_kwargs.items()
                     if k not in ('validated', 'query') and v is not None}
            if 'curie_or_iri' in rargs:  # curei_or_iri not in repr_args
                rargs['curie'] = self.curie
            self.set_next_repr(*rargs)
            if not self.iri:
                for k, v in rargs.items():
                    setattr(self, k, v)
                raise exc.NotFoundError(f'No results for {self!r}')
            else:
                log.warning(repr(self) + '\n')

            return
            # TODO this needs to go in a separate place, not here
            # and it needs to be easy to take a constructed term
            # and turn it into a term request
            for service in self.query.services:
                self.termRequests = []
                # FIXME configure a single term request service
                if hasattr(service, 'termRequest'):
                    makeRequest = service.termRequest(self)
                    termRequests.append(makeRequest)

        elif i > 0:
            raise exc.ManyResultsError(f'\nQuery {self.orig_kwargs} returned more than one result. '
                                       'Please review.\n')
        elif noId and not interactive:
            self.set_next_repr('curie', 'label')
            raise exc.NoExplicitIdError('Your term does not have a valid identifier.\n'
                                        f'Please replace it with {self!r}')


class TermRepr(OntTerm):
    repr_arg_order = (('curie', 'label', 'synonyms'),)
    repr_args = repr_arg_order[0]
    _oneshot_old_repr_args = None
    _firsts = 'curie', 'iri'

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
