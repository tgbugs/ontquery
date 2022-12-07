import rdflib
import requests
import ontquery as oq
import ontquery.exceptions as exc
from ontquery.utils import log, red
from ontquery.services import OntService


class rdflibLocal(OntService):  # reccomended for local default implementation
    #graph = rdflib.Graph()  # TODO pull this out into ../plugins? package as ontquery-plugins?
    # if loading if the default set of ontologies is too slow, it is possible to
    # dump loaded graphs to a pickle gzip and distribute that with a release...

    def __init__(self, graph, OntId=oq.OntId):
        self.OntId = OntId
        self.graph = graph
        self._curies = {cp:ip for cp, ip in self.graph.namespaces()}
        self.predicate_mapping = {'label': (rdflib.RDFS.label,),
                                  'term': (rdflib.RDFS.label,
                                           rdflib.URIRef(self.OntId('skos:prefLabel')),
                                           rdflib.URIRef(self.OntId('skos:altLabel')),
                                           rdflib.URIRef(self.OntId('skos:hiddenLabel')),
                                           rdflib.URIRef(self.OntId('NIFRID:synonym')),
                                           rdflib.URIRef(self.OntId('oboInOwl:hasSynonym')),
                                           rdflib.URIRef(self.OntId('oboInOwl:hasExactSynonym')),
                                           rdflib.URIRef(self.OntId('oboInOwl:hasNarroSynonym')),
                                           rdflib.URIRef(self.OntId('ilx.anno.hasExactSynonym:')),
                                           rdflib.URIRef(self.OntId('ilx.anno.hasNarrowSynonym:')),
                                  ),
                                  'definition': (
                                      rdflib.URIRef(self.OntId('definition:')),
                                      rdflib.URIRef(self.OntId('skos:definition')),
                                  ),
        }

        self._translate = {rdflib.RDFS.label:'label',
                           #rdflib.RDFS.subClassOf:'subClassOf',
                           #rdflib.RDF.type:'type',
                           #rdflib.OWL.disjointWith:'disjointWith',
                           #NIFRID.definingCitation:'definingCitation',

                           # doesn't quite work since we don't have the annotation model sorted right now
                           #rdflib.URIRef(self.OntId('ilx.anno.hasBroadSynonym:')): 'synonyms',
                           #rdflib.URIRef(self.OntId('ilx.anno.hasRelatedSynonym:')): 'synonyms',
                           #rdflib.URIRef(self.OntId('oboInOwl:hasBroadSynonym')): 'synonyms',
                           #rdflib.URIRef(self.OntId('oboInOwl:hasRelatedSynonym')): 'synonyms',

                           rdflib.URIRef(self.OntId('NIFRID:synonym')): 'synonyms',
                           rdflib.URIRef(self.OntId('oboInOwl:hasSynonym')): 'synonyms',
                           rdflib.URIRef(self.OntId('oboInOwl:hasExactSynonym')): 'synonyms',
                           rdflib.URIRef(self.OntId('oboInOwl:hasNarrowSynonym')): 'synonyms',

                           rdflib.URIRef(self.OntId('definition:')): 'definition',
                           rdflib.URIRef(self.OntId('skos:definition')): 'definition',
                    }

        super().__init__()

    @property
    def _onts(self):
        yield from self.graph[:rdflib.RDF.type:rdflib.OWL.Ontology]

    def add(self, iri, format):
        pass

    def setup(self, **kwargs):
        # graph is already set up...
        # assume that the graph is static for these
        super().setup(**kwargs)

    def debug(self):
        if self.graph:
            print(self.graph.serialize(format='nifttl').decode())

    @property
    def curies(self):
        return self._curies

    @property
    def predicates(self):
        yield from sorted(set(self.graph.predicates()))

    def by_ident(self, iri, curie, kwargs, predicates=tuple(), depth=1, _pseen=tuple()):
        def append_preds(out, c, o):
            if c not in out['predicates']:
                out['predicates'][c] = o  # curie to be consistent with OntTerm behavior
            elif isinstance(out['predicates'][c], str):
                out['predicates'][c] = out['predicates'][c], o
            else:
                out['predicates'][c] += o,

        def mergepreds(this_preds, prev_preds):
            if not prev_preds:
                return this_preds
            else:
                npreds = {**this_preds}
                for k, v in prev_preds.items():
                    if k in npreds:
                        if isinstance(v, tuple):
                            if isinstance(npreds[k], tuple):
                                npreds[k] = v + npreds[k]
                            else:
                                npreds[k] = v + (npreds[k],)
                        else:
                            if isinstance(npreds[k], tuple):
                                npreds[k] = (v,) + npreds[k]
                            else:
                                npreds[k] = v, npreds[k]

                return npreds

        predicates = tuple(rdflib.URIRef(p.iri)
                           # FIXME tricky here because we don't actually know the type
                           # of the predicate, it is a good bet that it will be an OntId
                           # of some extraction, but beyond that? who knows
                           if isinstance(p, self.OntId) else
                           p for p in predicates)
        out = {'predicates':{}}
        identifier = self.OntId(curie=curie, iri=iri)
        gen = self.graph.predicate_objects(rdflib.URIRef(identifier.iri))
        out['curie'] = identifier.curie
        out['iri'] = identifier.iri
        o = None
        owlClass = None
        owl = rdflib.OWL

        for p, o in gen:
            if isinstance(o, rdflib.BNode):
                continue

            pn = self._translate.get(p, None)
            if isinstance(o, rdflib.Literal):
                o = o.toPython()

            #elif p == rdflib.RDF.type and o == owl.Class:
            elif p == rdflib.RDF.type:  # XXX do not filter on type at this point
                if 'type' not in out:
                    out['type'] = o  # FIXME preferred type ...
                else:
                    if 'types' not in out:
                        out['types'] = out['type'],

                    out['types'] += o,  # TODO add test
                    # needs to be tuple for neurondm.OntTerm.query(search='a', prefix=('ilxtr',))

                owlClass = True  # FIXME ...

            elif p == rdflib.RDFS.subClassOf:
                owlClass = True
                # cardinality n > 1 fix
                c = self.OntId(p).curie
                if c not in out['predicates']:
                    out['predicates'][c] = tuple()  # force tuple

            if p == owl.deprecated and o:
                out['deprecated'] = True

            _o_already_done = False  # FIXME not quite right, also _out
            if pn is None:
                # TODO translation and support for query result structure
                # FIXME lists instead of klobbering results with mulitple predicates
                if isinstance(o, rdflib.URIRef):
                    o = self.OntId(o)  # FIXME we try to use OntTerm directly everything breaks
                    # FIXME these OntIds also do not derive from rdflib... sigh

                c = self.OntId(p).curie
                if c in _pseen and o in _pseen[c]:
                    _o_already_done = True
                else:
                    append_preds(out, c, o)

                #print(red.format('WARNING:'), 'untranslated predicate', p)
            else:
                c = pn
                if c in out and o not in out[c]:
                    if not isinstance(out[c], tuple):
                        out[c] = out.pop(c), o
                    else:
                        out[c] += o,
                else:
                    if c == 'synonyms':  # FIXME generalize probably
                        out[c] = o,
                    else:
                        out[c] = o

            if p in predicates and depth > 0 and not _o_already_done:
                # FIXME traverse restrictions on transitive properties
                # to match scigraph behavior
                try:
                    spout = next(self.by_ident(
                        o, None, {},
                        predicates=(p,),
                        depth=depth - 1,
                        _pseen=mergepreds(out['predicates'], _pseen)))
                    log.debug(f'{spout}')
                    if c in spout.predicates:
                        _objs = spout.predicates[c]
                        objs = _objs if isinstance(_objs, tuple) else (_objs,)
                        for _o in objs:
                            append_preds(out, c, _o)

                except StopIteration:
                    pass

        if o is not None and owlClass is not None:
            # if you yield here you have to yield from below
            yield self.QueryResult(kwargs, **out, _graph=self.graph, source=self)

    def _prefix(self, iri):
        try:
            prefix, _, _ = self.graph.compute_qname(iri, generate=False)
            return prefix
        except KeyError:
            return None

    def query(self, iri=None, curie=None, label=None, term=None, predicates=tuple(),
              search=None, prefix=tuple(), exclude_prefix=tuple(), all_classes=False,
              depth=1, **kwargs):
        _empty_tuple = tuple()  # FIXME name lookup cost vs empty tuple alloc cost
        if (prefix is not None and
            prefix is not _empty_tuple and
            all(a is None for a in (iri, curie, label, term))):
            if isinstance(prefix, str):
                prefix = prefix,

            for p in prefix:
                iri_prefix = self.graph.namespace_manager.store.namespace(p)
                if iri_prefix is not None:
                    # TODO is this faster or is shortening? this seems like it might be faster ...
                    # unless the graph has it all cached
                    for _iri in sorted(u for u in set(e for t in self.graph for e in t
                                                if isinstance(e, rdflib.URIRef))
                                       if self._prefix(u) == p):
                        yield from self.query(iri=_iri)

            return

        # right now we only support exact matches to labels FIXME
        kwargs['curie'] = curie
        kwargs['iri'] = iri
        kwargs['label'] = label
        kwargs['term'] = term
        kwargs['depth'] = depth
        kwargs['predicates'] = predicates

        #kwargs['term'] = term
        #kwargs['search'] = search
        #supported = sorted(self.QueryResult(kwargs))
        if all_classes:
            for iri, type in self.graph[:rdflib.RDF.type:]:
                if isinstance(iri, rdflib.URIRef):  # no BNodes
                    yield from self.by_ident(iri, None, kwargs,  # actually query is done here
                                             predicates=predicates,
                                             depth=depth - 1)
        elif iri is not None or curie is not None:
            yield from self.by_ident(iri, curie, kwargs,
                                     predicates=predicates,
                                     depth=depth - 1)
        elif search is not None:  # prevent search + prefix from behaving like prefix alone
            return
        else:
            for keyword, object in kwargs.items():
                if object is None:
                    continue

                # note that the predicate key is skipped because it is usually
                # only meaningful for querying via by_ident
                if keyword in self.predicate_mapping:
                    predicates = self.predicate_mapping[keyword]
                    for predicate in predicates:
                        gen = self.graph.subjects(predicate, rdflib.Literal(object))
                        for subject in gen:
                            if prefix or exclude_prefix:
                                oid = self.OntId(subject)
                                if prefix and oid.prefix not in prefix:
                                    continue

                                if exclude_prefix and oid.prefix in exclude_prefix:
                                    continue

                            yield from self.query(iri=subject)
                            return  # FIXME we can only search one thing at a time... first wins


class StaticIrisRemote(rdflibLocal):
    """ Create a Local from a remote by fetching the content at that iri """
    persistent_cache = False  # TODO useful for nwb usecase
    def __init__(self, *iris, OntId=oq.OntId):
        self.graph = rdflib.ConjunctiveGraph()
        for iri in iris:
            # TODO filetype detection from interlex
            resp = requests.get(iri)
            if resp.ok:
                ttl = resp.content
                self.graph.parse(data=ttl, format='turtle')
            else:
                raise exc.FetchingError(f'Could not fetch {iri} {resp.status_code} {resp.reason}')

        super().__init__(self.graph, OntId=OntId)


class GitHubRemote(StaticIrisRemote):  # TODO very incomplete
    """ Create a Local from a file on github from group, repo, and filename """
    base_iri = ('https://raw.githubusercontent.com/'
                '{group}/{repo}/{branch_or_commit}/{filepath}')
    def __init__(self, group, repo, *filepaths,
                 branch='master',
                 commit=None,  # mutually exclusive with branch, or error on commit not on branch?
                 branches_or_commits=('master',),
                 OntId=oq.OntId):
        """ filepath from the working directory no leading slash """
        # TODO > 1 group, there are too many combinations here
        # use case would be to load all the relevant files from each of the
        # branches parcellation, neurons, methods, sparc
        # to do this with scigraph we could have a function that produced
        # the yaml template that loads the output of self.iris
        self.filepaths = filepaths
        self.groups_repos_branches = (group, repo, branch),
        super().__init__(*self.iris, OntId=OntId)

    @property
    def iris(self):
        for group, repo, branch_or_commit in self.groups_repos_branches:
            for filepath in self.filepaths:
                yield self.base_iri.format(group=group,
                                           repo=repo,
                                           branch_or_commit=branch_or_commit,
                                           filepath=filepath)
