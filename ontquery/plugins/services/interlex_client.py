from copy import deepcopy
import json
from typing import Optional, Union, List, Tuple, Any

from rdflib import URIRef
from requests import Response

from . import deco
from .interlex_session import InterlexSession
from ontquery.utils import log
from ontquery import exceptions as exc


@deco.interlex_api_key
class InterLexClient(InterlexSession):
    """ Connects to SciCrunch via its' api endpoints

    Purpose is to allow external curators to add entities and annotations to
    those entities.

    Functions To Use:
        add_entity
        add_annotation

    Notes On Time Complexity:
        Function add_entity, if added an entity successfully, will hit a
        least 5 endpoints. This may cause it to take a few seconds to load
        each entity into SciCrunch. Function add_annotation is a little more
        forgiving with it only hitting 3 minimum.
    """

    Error = InterlexSession.Error

    class SuperClassDoesNotExistError(Error):
        """The superclass listed does not exist!"""

    class EntityDoesNotExistError(Error):
        """The entity listed does not exist!"""

    class AlreadyExistsError(Error):
        """The entity or entity's meta listed already exists!"""

    class DoesntExistError(Error):
        """The entity or entity's meta you want to update doesn't exist!"""

    class BadResponseError(Error):
        """Response did not return a 200s status."""

    class NoLabelError(Error):
        """Need label for new entity."""

    class NoTypeError(Error):
        """New Entities need a type given."""

    NoApiKeyError = exc.NoApiKeyError

    class MissingKeyError(Error):
        """Missing dict key for scicrunch entity for API endpoint used."""

    class IncorrectKeyError(Error):
        """Incorrect possible dictionary key for scicrunch entity."""

    class IncorrectAPIKeyError(Error):
        """Incorrect API key for scicrunch website used."""

    class IncorrectAuthError(Error):
        """Incorrect authentication key for testing websites."""

    default_base_url = 'https://scicrunch.org/api/1/'
    ilx_base_url = 'http://uri.interlex.org/base/'
    entity_types = (
        'term',
        'TermSet',
        'pde',
        'cde',
        'fde',
        'annotation',
        'relationship',
    )

    def __init__(self,
                 base_url: str = default_base_url,
                 key: str = None,):
        """ SciCrunch's InterLex API init for add/update functions.

            InterLex API Delete functions on entity level do not exist. Please test on
            https://test3.scicrunch.org/api/1/ first for base_url. If mistakes are made on entities,
            a log is created

        :rtype: object
        :param str base_url: complete SciCrunch API base_url.
        :param str key: API key for SciCrunch.
        """
        key = key or self.api_key  # Set in config under scigraph-api-key or interlex-api-key
        InterlexSession.__init__(self, key=key, host=base_url)

    @staticmethod
    def get_ilx_fragment(ilx_id: str, fragment: bool = False) -> str:
        """ Convert InterLex ID or IRI to its fragment alternative (ie ilx_#)

            :param str ilx_id: InterLex ID or IRI.
            :return: str

            >>> get_ilx_fragment('http://uri.interlex.org/base/ilx_0101431')
            ilx_0101431
            >>> get_ilx_fragment('ILX:0101431')
            ilx_0101431
        """
        if not ilx_id:
            raise ValueError(f'ILX ID cannot be None!')
        ilx_id = ilx_id.rsplit('/', 1)[-1]
        if ilx_id[:3].lower() not in ['tmp', 'ilx', 'pde', 'cde']:
            raise ValueError(f"Provided ID {ilx_id} could not be determined as InterLex ID.")
        return ilx_id.replace(':', '_').lower()

    def get_ilx_iri(self, ilx_id: str) -> str:
        """
        Makes Sure InterLex ID is in it's proper IRI form.

        Args:
            ilx_id (str): InterLex fragment, IRI, curie

        Returns:
            str: InterLex IRI
        """
        fragment = self.get_ilx_fragment(ilx_id)
        return f'http://uri.interlex.org/base/{fragment}'

    @staticmethod
    def _check_type(element: Any,
                    types: Union[Any, List[Any]]) -> Any:
        """ Check if element is an  accepted types provided.

            :param element: Field value.
            :param types: Usable types
            :return: Original element
        """
        if not isinstance(element, types):
            TypeError(f"Element {element} needs to be of type {types}")
        return element

    @staticmethod
    def _check_value(element: Any,
                     values: tuple) -> Any:
        """ Check if element is in accepted values provided.

            :param element: Field value.
            :param values: Hardcoded values SciCrunch expects.
            :return: Original element
        """
        if element not in values:
            ValueError(f"Element {element} needs to be a value from {values}")
        return element

    def _check_dict(self, element: dict, ref: dict) -> Any:
        """ Makes sure dictionary fields make key value and value type

        :param element: target dictionary
        :param ref: reference dictionary
        :return: Original element
        :raises: MissingKeyError

        >>> self._check_dict({'type':'exact'}, ref={'literal':str})
        MissingKeyError
        >>> self._check_dict({'literal':'Brain', 'type':'exact'}, ref={'literal':str})
        {'literal':'Brain', 'type':'exact'}
        """
        for key, value in ref.items():
            if not element.get(key):
                raise self.MissingKeyError(f"Missing key {key} in dictionary {element}")
            self._check_type(element[key], value)

    def _process_field(self,
                       field: Union[str, int],
                       accepted_types: tuple,
                       accepted_values: tuple = None,) -> Union[str, int]:
        """ Check if single field is following guidelines for type and/or value acceptance

        :param accepted_types: Review if field is a usable type.
        :param accepted_values: Hard check if field value is in accepted values.
        :return: Original field
        """
        self._check_type(field, accepted_types)
        if accepted_values:
            self._check_value(field, accepted_values)
        return field

    @staticmethod
    def _remove_records(ref_records: List[dict],
                        records: List[dict],
                        on: Union[List[str], str],) -> List[dict]:
        """ Removes match records on field value matches.

        :param on: Exact composite key value check.
        """
        if isinstance(on, str):
            on = [on]
        old_indexes_to_remove = []
        for i, ref_record in enumerate(ref_records):
            for record in records:
                on_hit = all([
                    True if ref_record[key].lower().strip() == record.get(key, '').lower().strip()
                    else False
                    for key in on
                ])
                if on_hit is True:
                    old_indexes_to_remove.append(i)
        for i in sorted(old_indexes_to_remove, reverse=True):
            ref_records.pop(i)
        return ref_records

    @staticmethod
    def _merge_records(ref_records: List[dict],
                       records: List[dict],
                       on: Union[List[str], str] = None,
                       alt: Union[List[str], str] = None,
                       passive: bool = False,) -> List[dict]:
        """ Merge records
            "on" specified fields.
            "alt" update record if ref record is missing data.
            "passive" append instead of update on "alt" version.

        :param on: Exact composite key value check.
        :param alt: Fields to logically update if exact keys all match.
        :param passive: Append instead of update record if alt is found.
        """
        # Makes sure merge is never empty
        clean = lambda s: s.lower().strip()
        on = on or []
        alt = alt or []
        if on is []:
            on = list(ref_records)
        if isinstance(on, str):
            on = [on]
        if isinstance(alt, str):
            alt = [alt]
        # duplicate records to be removed before being added to ref records
        new_indexes_to_remove = []
        # Judge if an of the records are new
        for i, record in enumerate(records):
            for j, ref_record in enumerate(ref_records):
                # True if unique keys match
                on_hit = all([
                    True if clean(ref_record[key]) == clean(record.get(key, ''))
                    else False
                    for key in on
                ])
                # If no match
                if on_hit is False:
                    continue
                # If a match with no second chances, it already exists
                if on_hit is True and alt is []:
                    new_indexes_to_remove.append(i)
                    break
                # True if any differences in non-unique keys
                alt_hit = any([
                    True if (clean(ref_record[key]) != clean(record.get(key, ''))) and (not ref_record[key])
                    else False
                    for key in alt
                ])
                # Failed second chance, it already exists
                if alt_hit is False:
                    new_indexes_to_remove.append(i)
                    break
                # Will just add matches to end if passive is True
                if passive is False:
                    # Remove new record since it's merge into old record
                    new_indexes_to_remove.append(i)
                    # Update old record with matched new record at alt keys #
                    for key in alt:
                        if (not ref_record[key]) and (record.get(key)):
                            ref_record[key] = record[key]
        for i in sorted(new_indexes_to_remove, reverse=True):
            records.pop(i)
        return ref_records + records

    @staticmethod
    def _remove_duplicate_records(records: List[dict],
                                  on: Union[List[str], str],) -> List[dict]:
        unique_records = []
        visited = {}
        for record in records:
            value_set = tuple((on_item, record[on_item]) for on_item in on)
            if visited.get(value_set):
                continue
            unique_records.append(record)
            visited[value_set] = True
        return unique_records

    def _process_synonyms(self, synonyms: Union[List[dict], List[str]]) -> List[dict]:
        """ Make sure synonyms match indented input.

        :param synonyms: Synonyms of entity.
        """
        corrected_synonyms = []
        # Guarantee synonym default
        if not synonyms:
            return []
        self._check_type(synonyms, (str, dict, list))
        # In case user only has a single input
        if isinstance(synonyms, (str, dict)):
            synonyms = [synonyms]
        # For each synonym -- transform
        for synonym in synonyms:
            self._check_type(synonym, (str, dict))
            if isinstance(synonym, str):
                synonym = {'literal': synonym, 'type': '', }
            elif isinstance(synonym, dict):
                self._check_dict(synonym, ref={'literal': str})
                synonym = {'literal': synonym['literal'], 'type': synonym.get('type', '') or '', }
            else:
                self._check_type(synonym, (str, dict))
            corrected_synonyms.append(synonym)
        corrected_synonyms = self._remove_duplicate_records(corrected_synonyms, on=['literal', 'type'])
        return corrected_synonyms

    def _process_superclass(self, superclass: str) -> Optional[List[dict]]:
        if not superclass:
            return None
        superclass = self.get_ilx_fragment(superclass)
        return [{'ilx': superclass}]

    def _process_existing_ids(self, existing_ids: List[dict]) -> List[dict]:
        """ Making sure existing_id items are in proper format for entity.

        :param List[dict] existing_ids: Alternative IDs for the entity.
        :return: List[dict]

        >>> self._process_existing_ids( \
                existing_ids=[{ \
                    'iri': 'http://uri.interlex.org/base/ilx_1234567', \
                    'curie': 'ILX:1234567',  # Obeys prefix:id structure. \
                    'preferred': '0',  # Can be 0 or 1 with a type of either str or int. \
                }] \
            )
        """

        def fix_existing_ids_preferred(_existing_ids: List[dict],
                                       ranking: list = None) -> List[dict]:
            """ Give value 1 to top preferred existing id; 0 otherwise.

                Will using the ranking list to score each existing id curie prefix
                and will sort top preferred to the top. Top will get preferred = 1,
                the rest will get 0.

            :param _existing_ids: entities existing ids.
            :param ranking: custom ranking for existing ids. Default: None
            :return: entity existing ids preferred field fixed based on ranking.
            """
            _existing_ids = self._remove_duplicate_records(_existing_ids, on=['curie', 'iri'])
            ranked_existing_ids: List[Tuple[int, dict]] = []
            preferred_fixed_existing_ids: List[dict] = []
            if not ranking:
                ranking = [
                    'CHEBI',
                    'NCBITaxon',
                    'COGPO',
                    'CAO',
                    'DICOM',
                    'UBERON',
                    'FMA',
                    'NLX',
                    'NLXANAT',
                    'NLXCELL',
                    'NLXFUNC',
                    'NLXINV',
                    'NLXORG',
                    'NLXRES',
                    'NLXSUB'
                    'BIRNLEX',
                    'SAO',
                    'NDA.CDE',
                    'PR',
                    'IAO',
                    'NIFEXT',
                    'OEN',
                    'MESH',
                    'NCIM',
                    'ILX.SET',
                    'ILX.PDE',
                    'ILX.CDE',
                    'npokb',
                    # 'ILX',
                ]
            # will always be larger than last index :)
            default_rank = len(ranking)
            # prefix to rank mapping
            ranking = {prefix: ranking.index(prefix) for prefix in ranking}
            # using ranking on curie prefix to get rank
            for ex_id in _existing_ids:
                prefix = ex_id['curie'].split(':')[0]
                rank = ranking[prefix] if ranking.get(prefix) else default_rank
                ranked_existing_ids.append((rank, ex_id))
            # sort existing_id curie prefixes ASC using ranking as a reference
            sorted_ranked_existing_ids = sorted(ranked_existing_ids, key=lambda x: x[0])
            # update preferred to proper ranking and append to new list
            for i, rank_ex_id in enumerate(sorted_ranked_existing_ids):
                rank, ex_id = rank_ex_id
                if i == 0:
                    ex_id['preferred'] = 1
                else:
                    ex_id['preferred'] = 0
                preferred_fixed_existing_ids.append(ex_id)
            preferred_fixed_existing_ids = self._remove_duplicate_records(preferred_fixed_existing_ids, on=['curie', 'iri'])
            return preferred_fixed_existing_ids

        corrected_existing_ids = []
        self._check_type(existing_ids, list)
        for existing_id in existing_ids:
            self._check_type(existing_id, dict)
            self._check_dict(existing_id, ref={'curie': str, 'iri': (str, URIRef)})
            corrected_existing_ids.append({
                'iri': str(self._check_type(existing_id['iri'], (str, URIRef))),  # todo : replace checktype with expand
                'curie': self._check_type(existing_id['curie'], str),  # todo : replace checktype with qname
                'preferred': existing_id.get('preferred', '0'),
            })
        return fix_existing_ids_preferred(corrected_existing_ids)

    def query_elastic(self,
                      term: str = None,
                      label: str = None,
                      query: dict = None,
                      **kwargs) -> Optional[List[dict]]:
        """ Queries Elastic for term (wild card) or raw query to elastic.

        :param str term: wild card value to be searched throughout entities.
        :param str label: direct exact matching for label & synonym fields.
        :param dict query: raw query for elastic where {"query":{?}} as input.
        :return: list of all possible entity hits in their nested dict format.

        # Say we want "brain" entity.
        >>> query_elastic(term='brains') # random results
        >>> query_elastic(label='Brains') # will actually get you brain
        # Returns [], but this is just to show the format of body field.
        >>> query_elastic(body={"query": {"match": {"label": "brains"}}})
        # Therefore if you are interested in "real" hits use label
        # or custom body field.
        """
        params = {
            'size': '10',
            'from': '0',
            **kwargs,
        }
        if query:
            params['query'] = json.dumps(query.get('query', query))  # self return if user gives body of query
        elif label:
            params['term'] = label
        elif term:
            params['term'] = term
        else:
            return
        resp = self._get('term/elastic/search', params=params)
        entities = resp.json()['data']['hits']['hits']  # Not a mistake; elastic nests the hits twice
        # Also not a mistake; actual metadata is inside _source
        if entities:
            entities = [entity['_source'] for entity in entities]
            # Damn elasticsearch doesn't have a true exact match. We need to double check the output
            if label:
                exact_entities = []
                for entity in entities:
                    if label.strip().lower() == entity['label'].strip().lower():
                        exact_entities.append(entity)
                    elif label.strip().lower() in [syn['literal'].strip().lower() for syn in entity['synonyms']]:
                        exact_entities.append(entity)
                entities = exact_entities
        return entities

    def get_entity(self, ilx_id: str) -> dict:
        """ Get full Entity metadata from its ILX ID.

        :param str ilx_id: ILX ID of current Entity.
        """
        ilx_id = self.get_ilx_fragment(ilx_id)
        resp = self._get(f"term/ilx/{ilx_id}")
        entity = resp.json()['data']
        return entity

    # todo even in test env it needs ILX prefix instead of TMP b/c its anchored to existing_ids
    def get_entity_from_curie(self, curie: str) -> dict:
        """ Pull InterLex entity if curie exists in existing_ids

        :param curie: Compressed version of IRI from entity

        >>> self.get_entity_from_curie('UBERON:6000015')
        """
        return self._get(f'term/curie/{curie}').json()['data']

    def add_entity(self,
                   label: str,
                   type: str,
                   cid: str = None,
                   definition: str = None,
                   comment: str = None,
                   superclass: str = None,
                   synonyms: list = None,
                   existing_ids: list = None,
                   force: bool = False,
                   **kwargs) -> dict:
        """ Add Interlex entity into SciCrunch.

            Loosely structured ontological data based on the source ontologies for readability.

        :param label: Preferred name of entity.
        :param type: Any of the following: term, TermSet, cde, pde, fde, relationship, annotation.
        # todo add description of each type here
        :param cid: Community ID
        :param definition: Entities official definition.
        :param comment: A foot note regarding either the interpretation of the data or the data itself
        :param superclass: The ilx_id of the parent of this entity. Example: Organ is a superclass to Brain
        :param synonyms: Alternate names of the label.
        :param existing_ids: Alternate/source ontological iri/curies. Can only be one preferred ID.
        :param force: If entity is different from existing entity. This will add it if you have admin privileges.
        :param kwargs: a net for extra unneeded paramters.
        :return: requests.Response of insert or query from existing.

        >>> self.add_entity( \
                label='Brain', \
                type='term',  # options: term, pde, fde, cde, annotation, or relationship \
                definition='Official definition for entity.', \
                comment='Additional casual notes for the next person.', \
                superclass='ilx_1234567', \
                synonyms=[{ \
                    'literal': 'Brains',  # label of synonym \
                    'type': 'obo:hasExactSynonym',  # Often predicate defined in ref ontology. \
                }], \
                existing_ids=[{ \
                    'iri': 'http://purl.obolibrary.org/obo/UBERON_0000955', \
                    'curie': 'UBERON:0000955',  # Obeys prefix:id structure. \
                    'preferred': '1',  # Can be 0 or 1 with a type of either str or int. \
                }], \
            )
        """
        synonyms = synonyms or []
        existing_ids = existing_ids or []
        entity = {
            'label': self._process_field(label, accepted_types=(str,)),
            'type': self._process_field(type, accepted_values=self.entity_types, accepted_types=(str,)),
            'cid': self._process_field(cid, accepted_types=(str, int)),
            'definition': self._process_field(definition, accepted_types=(str,)),
            'comment': self._process_field(comment, accepted_types=(str,)),
            'superclasses': self._process_superclass(superclass),
            'synonyms': self._process_synonyms(synonyms),
            'existing_ids': self._process_existing_ids(existing_ids),
            'force': force,
        }
        #entity['batch-elastic'] = 'true'
        resp = self._post('term/add', data=deepcopy(entity))
        entity = resp.json()['data']
        if resp.status_code == 200:
            log.warning(f"You already added {entity['label']} with InterLex ID {entity['ilx']}")
        # Backend handles more than one. User doesn't need to know.
        entity['superclass'] = entity.pop('superclasses')
        if entity['superclass']:
            entity['superclass'] = 'http://uri.interlex.org/base/' + entity['superclass'][0]['ilx']
        # todo: match structure of input
        # todo: compare if identical; for now test_interlex_client will do
        return entity

    def deprecate_entity(self, ilx_id: str) -> dict:
        """ Annotates for deprecation while updating the status on databases.

            status =  0 :: active
            status = -1 :: hidden
            status = -2 :: deleted

            Note the point is not to actually delete the entity.

        :param ilx_id: ILX ID of entity to be removed.
        :return: Deprecated Record of entity.
        """
        deprecated_id = 'http://uri.interlex.org/base/ilx_0383241'  # deprecated entity
        deprecated = self.get_entity(deprecated_id)
        if (deprecated['label'] != 'deprecated') or (deprecated['type'] != 'annotation'):
            raise ValueError('Oops! Annotation "deprecated" was move. Please update deprecated')
        # ADD DEPRECATED ANNOTATION
        annotation = self.add_annotation(
            term_ilx_id=ilx_id,
            annotation_type_ilx_id=deprecated_id,
            annotation_value='True',
        )
        if annotation['value'] != 'True':
            raise ValueError('Deprecation annotation was not added correctly!')
        log.info(annotation)
        # GIVE STATUS -2
        update = self.update_entity(ilx_id=ilx_id, status='-2')
        if update['status'] != '-2':
            raise ValueError('Entity status for deprecation failed!')
        log.info(update)
        return update

    def replace_entity(self, ilx_id: str, replaced_by_ilx_id: str) -> dict:
        """ Create a relationship between an entity that is being deprecated and replaced by another entity.

        :param ilx_id: ILX ID of Entity to be replaced.
        :param replaced_by_ilx_id: ILX ID of new Entity that is now being used.
        :return: Deprecated Record of entity.
        """
        replaced_by_id = 'http://uri.interlex.org/base/ilx_0383242'  # replacedBy entity
        replaced_by = self.get_entity(replaced_by_id)
        if (replaced_by['label'] != 'replacedBy') or (replaced_by['type'] != 'relationship'):
            raise ValueError('Oops! "replacedBy" was move. Please update ILX for "Replaced By" annotation')
        # ADD RELATIONSHIP CONNECTION FROM OLD TO NEW ENTITY
        relationship = self.add_relationship(
            entity1_ilx=ilx_id,
            relationship_ilx=replaced_by_id,
            entity2_ilx=replaced_by_ilx_id,
        )
        log.info(relationship)
        return self.deprecate_entity(ilx_id)

    def merge_and_replace_entity(self, from_ilx_id: str, to_ilx_id: str) -> dict:
        entity = self.get_entity(to_ilx_id)
        deprecated_entity = self.get_entity(from_ilx_id)
        # 1 to 1 FIELDS
        for field in ['definition', 'comment']:
            if not entity[field]:
                entity[field] = deprecated_entity[field]
        # todo add old superclass to annotations
        if not entity['superclasses'] and deprecated_entity['superclasses']:
            entity['superclasses'] = [{'superclass_tid': deprecated_entity['superclasses'][0]['id']}]
        # todo add old label as synonym if different
        # SYNONYM
        entity['synonyms'] = self._merge_records(
            ref_records=entity.get('synonyms', []),
            records=[{'literal':d['literal'], 'type':d['type']} 
                      for d in deprecated_entity.get('synonyms', [])
                      if d['literal'].lower().strip() != entity['label'].lower().strip()],
            on=['literal'],
            alt=['type'],
        )        
        # EXISTING ID
        entity['existing_ids'] += [
            {'iri': d['iri'], 'curie': d['curie'], 'preferred':d['preferred']}
            for d in deprecated_entity.get('existing_ids', [])
            if not d['iri'].startswith('http://uri.interlex.org/base/')
        ]
        # RELATIONSHIP
        for relationship in deprecated_entity['relationships']:
            if str(relationship['withdrawn']) != '0':
                continue
            if from_ilx_id == relationship['term1_ilx']:
                entity1_ilx = to_ilx_id
                entity2_ilx = relationship['term2_ilx']
            else:
                entity1_ilx = relationship['term1_ilx']
                entity2_ilx = to_ilx_id
            self.add_relationship(entity1_ilx, relationship['relationship_term_ilx'], entity2_ilx)
        # # ANNOTATION
        for annotation in deprecated_entity['annotations']:
            if str(annotation['withdrawn']) != '0': 
                continue
            self.add_annotation(to_ilx_id, annotation['annotation_term_ilx'], annotation['value'])
        # ReplaceBy relationship connection
        self.replace_entity(from_ilx_id, to_ilx_id)
        # POST
        resp = self._post(f"term/edit/{entity['ilx']}", data=entity)
        # BUG: server response is bad and needs to actually search again to get proper format
        entity = resp.json()['data']
        entity['superclass'] = entity.pop('superclasses')
        if entity['superclass']:
            entity['superclass'] = 'http://uri.interlex.org/base/' + entity['superclass'][0]['ilx']
        # todo add a sanity check here
        return entity

    def partial_update(self,
                       curie: str = None,
                       definition: str = None,
                       comment: str = None,
                       superclass: str = None,
                       synonyms: List[dict] = None,
                       existing_ids: List[dict] = None,) -> dict:
        """ Update entity field only if the reference field is empty.

        :param curie: Curie of entity within existing ids.
        :param definition: Entities official definition.
        :param comment: A foot note regarding either the interpretation of the data or the data itself
        :param superclass: The ilx_id of the parent of this entity. Example: Organ is a superclass to Brain
        :param synonyms: Alternate names of the label.
        :param existing_ids: Alternate/source ontological iri/curies. Can only be one preferred ID.
        """
        if any([True if curie.lower().startswith(prefix) else False for prefix in
                ['tmp_', 'tmp:', 'ilx_', 'ilx:']]):
            entity = self.get_entity(curie)
        else:
            entity = self.get_entity_from_curie(curie)
        if entity['ilx'] is None:
            raise ValueError(f'curie [{curie}] does not exist yet in InterLex.')
        response = self.update_entity(
            ilx_id=entity['ilx'],
            definition=definition if not entity['definition'] else None,
            comment=comment if not entity['comment'] else None,
            superclass=superclass if not entity['superclasses'] else None,
            add_existing_ids=existing_ids or [],
            add_synonyms=synonyms or [],
        )
        return response

    def update_entity(self,
                      ilx_id: str,
                      label: str = None,
                      type: str = None,
                      definition: str = None,
                      comment: str = None,
                      superclass: str = None,
                      cid: str = None,
                      status: str = None,
                      add_synonyms: Union[List[dict], List[str]] = None,
                      delete_synonyms: Union[List[dict], List[str]] = None,
                      add_existing_ids: List[dict] = None,
                      delete_existing_ids: List[dict] = None, ) -> dict:
        """ Updates pre-existing entity as long as the api_key is from the account that created it.

            :param ilx_id: Interlex IRI, curie, or fragment of entity to update.
            :param label: Name of entity.
            :param type: InterLex entities type: term, cde, fde, pde, annotation, or relationship
            :param definition: Entities official definition.
            :param comment: A foot note regarding either the interpretation of the data or the data itself
            :param superclass: The ilx_id of the parent of this entity. Example: Organ is a superclass to Brain
            :param cid: Community ID.
            :param status: Entity status.
                -2 : Withdrawn; entity is no longer searchable and is not visible
                -1 : Under review; entity is visible
                0 : No action needed; entity is visible
            :param add_synonyms: Synonyms to add if they don't already exist.
            :param delete_synonyms: Synonyms to delete.
            :param add_existing_ids: Add alternative IRIs if they don't already exist.
            :param delete_existing_ids: Delete alternative IRIs.
            :return: Server response that is a nested dictionary format

            >>> self.update_entity( \
                ilx_id='ilx_0101431', \
                label='Brain', \
                type='term',  # options: term, pde, fde, cde, annotation, or relationship \
                definition='Official definition for entity.', \
                comment='Additional casual notes for the next person.', \
                superclass='ilx_1234567', \
                add_synonyms=[{ \
                    'literal': 'Better Brains',  # label of synonym \
                    'type': 'obo:hasExactSynonym',  # Often predicate defined in ref ontology. \
                }], \
                delete_synonyms=[{ \
                    'literal': 'Brains',  # label of synonym \
                    'type': 'obo:hasExactSynonym',  # Often predicate defined in ref ontology. \
                }], \
                add_existing_ids=[{ \
                    'iri': 'http://purl.obolibrary.org/obo/UBERON_0000956', \
                    'curie': 'UBERON:0000956',  # Obeys prefix:id structure. \
                    'preferred': '1',  # Can be 0 or 1 with a type of either str or int. \
                }], \
                delet_existing_ids=[{ \
                    'iri': 'http://purl.obolibrary.org/obo/UBERON_0000955', \
                    'curie': 'UBERON:0000955',  # Obeys prefix:id structure. \
                }], \
                cid='504',  # SPARC Community, \
                status='0',  # remove delete \
            )
        """
        ilx_id = self.get_ilx_fragment(ilx_id)
        template_entity_input = {k: v for k, v in locals().copy().items() if k != 'self'}
        if template_entity_input.get('superclass'):
            template_entity_input['superclass'] = self.get_ilx_fragment(template_entity_input['superclass'])
        if add_synonyms or delete_synonyms or add_existing_ids or delete_existing_ids or superclass:
            existing_entity = self.get_entity(ilx_id)
            existing_entity.pop('curie')
            existing_entity.pop('annotations')
            if not existing_entity['id']:
                raise self.EntityDoesNotExistError(f'ilx_id provided {ilx_id} does not exist')
        else:
            existing_entity = {'ilx': ilx_id}
        if label:
            existing_entity['label'] = label
        if type:
            existing_entity['type'] = type
        if definition:
            existing_entity['definition'] = definition
        if comment:
            existing_entity['comment'] = comment
        if superclass:
            existing_entity['superclasses'] = self._process_superclass(superclass)
        # BUG: superclass needs id as superclass_tid
        elif existing_entity.get('superclasses'):
            existing_entity['superclasses'] = [{'superclass_tid': existing_entity['superclasses'][0]['id']}]
        if cid:
            existing_entity['cid'] = cid
        if status:
            existing_entity['status'] = status
        # Clean duplicates in these entities. 
        # API does not have the same filters as Interface so this step is needed.
        # TODO duplicate annotation php to syn and exids so we can remove this if possible
        existing_entity['synonyms'] = self._remove_duplicate_records(
            existing_entity.get('synonyms', []), 
            on=['literal', 'type'],
        )
        existing_entity['existing_ids'] = self._remove_duplicate_records(
            existing_entity.get('existing_ids', []), 
            on=['curie', 'iri'],
        )
        # delete is before add to give a sudo update functionality
        if delete_synonyms:
            existing_entity['synonyms'] = self._remove_records(
                ref_records=existing_entity.get('synonyms', []),
                records=self._process_synonyms(delete_synonyms),
                on=['literal', 'type'],
            )
        if add_synonyms:
            existing_entity['synonyms'] = self._merge_records(
                ref_records=existing_entity.get('synonyms', []),
                records=self._process_synonyms(add_synonyms),
                on=['literal'],
                alt=['type']
            )
        if delete_existing_ids:
            existing_entity['existing_ids'] = self._remove_records(
                ref_records=existing_entity.get('existing_ids', []),
                records=self._process_existing_ids(delete_existing_ids),
                on=['curie', 'iri'],
            )
        if add_existing_ids:
            existing_entity['existing_ids'] = self._merge_records(
                ref_records=existing_entity.get('existing_ids', []),
                records=self._process_existing_ids(add_existing_ids),
                on=['curie', 'iri'],
            )
        if existing_entity['existing_ids']:
            existing_entity['existing_ids'] = self._process_existing_ids(existing_entity['existing_ids'])
        # existing_entity['batch-elastic'] = 'true'
        resp = self._post(f"term/edit/{existing_entity['ilx']}", data=existing_entity)
        # BUG: server response is bad and needs to actually search again to get proper format
        entity = resp.json()['data']
        entity['superclass'] = entity.pop('superclasses')
        if entity['superclass']:
            entity['superclass'] = 'http://uri.interlex.org/base/' + entity['superclass'][0]['ilx']
        # todo add a sanity check here
        return entity

    def get_annotation_via_tid(self, tid: str) -> dict:
        """ Gets Annotation by its term id.

        :param tid: Term ID.
        :return: Record of InterLex entity Annotation.

        # todo add example
        """
        return self._get(f'term/get-annotations/{tid}').json()['data']

    def add_annotation(self,
                       term_ilx_id: str,
                       annotation_type_ilx_id: str,
                       annotation_value: str,
                       real_server_resp: bool = False) -> dict:
        """ Adding an annotation value to a prexisting entity

            An annotation exists as 3 different parts ([1] -> [2] -> [3]):
                1. entity with type term, TermSet, cde, fde, or pde
                2. entity with type annotation
                3. string value of the annotation

            :param term_ilx_id: Term ILX ID
            :param annotation_type_ilx_id: Annototation ILX ID
            :param annotation_value: Annotation value
            :param real_server_resp: Will return term IDs and versions, not InterLex IDs. 
            :return: Annotation Record

            >>> self.add_annotation(
                    term_ilx_id='ilx_0101431',  # brain ILX ID
                    annotation_type_ilx_id='ilx_0381360',  # hasDbXref ILX ID
                    annotation_value='http://neurolex.org/wiki/birnlex_796'  # any string value
                )
        """
        tid = self.get_ilx_fragment(term_ilx_id)
        annotation_tid = self.get_ilx_fragment(annotation_type_ilx_id)
        data = {'tid': tid,
                'annotation_tid': annotation_tid,
                'value': annotation_value}
        resp = self._post('term/add-annotation', data={**data, **{'batch-elastic': 'true'}})
        if resp.status_code == 200:
            log.warning(f"Annotation: "
                        f"[{data['tid']}] -> [{data['annotation_tid']}] -> [{data['value']}]"
                        f"has already been added")
        if real_server_resp:
            data = resp.json()['data']
        return data

    def withdraw_annotation(self,
                        term_ilx_id: str,
                        annotation_type_ilx_id: str,
                        annotation_value: str) -> Optional[dict]:
        """ If annotation doesnt exist, add it

            :param term_ilx_id: Term ILX ID
            :param annotation_type_ilx_id: Annototation ILX ID
            :param annotation_value: Annotation value
            :return: Empty Annotation Record
        """
        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            raise self.EntityDoesNotExistError(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            raise self.EntityDoesNotExistError(
                'annotation_type_ilx_id: ' + annotation_type_ilx_id
                + ' does not exist'
            )
        entity_annotations = self.get_annotation_via_tid(term_data['id'])
        annotation_id = ''
        for annotation in entity_annotations:
            if str(annotation['tid']) == str(term_data['id']):
                if str(annotation['annotation_tid']) == str(anno_data['id']):
                    if str(annotation['value']) == str(annotation_value):
                        annotation_id = annotation['id']
                        break
        if not annotation_id:
            log.warning('Annotation you wanted to delete does not exist')
            return None
        data = {
            'tid': term_data['id'],  # for delete
            'annotation_tid': anno_data['id'],  # for delete
            'value': annotation_value,  # for delete
            'term_version': term_data['version'],
            'annotation_term_version': anno_data['version'],
            'withdrawn': '1',
        }
        output = self._post(f"term/edit-annotation/{annotation_id}", data=data).json()['data']
        return output

    def get_relationship_via_tid(self, tid: str) -> dict:
        """ Get Entity Relationship by its term ID.

        :param tid: Term ID
        :return: Record of InterLex entity Relationship.

        # todo add example
        """
        return self._get(f'term/get-relationships/{tid}').json()['data']

    def add_relationship(self,
                         entity1_ilx: str,
                         relationship_ilx: str,
                         entity2_ilx: str,
                         real_server_resp: bool = False) -> dict:
        """ Adds relationship connection in Interlex

        A relationship exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type relationship that connects entity1 to entity2
                -> Has its' own meta data, so no value needed
            3. entity with type term, cde, fde, or pde
        """
        entity1_ilx = self.get_ilx_fragment(entity1_ilx)
        relationship_ilx = self.get_ilx_fragment(relationship_ilx)
        entity2_ilx = self.get_ilx_fragment(entity2_ilx)
        data = {'term1_id': entity1_ilx,
                'relationship_tid': relationship_ilx,
                'term2_id': entity2_ilx}
        # resp = self._post('term/add-relationship', data={**data, **{'batch-elastic': 'true'}})
        resp = self._post('term/add-relationship', data=data)

        if resp.status_code == 200:
            log.warning(f"Relationship:"
                        f" [{data['term1_id']}] -> [{data['relationship_tid']}] -> [{data['term2_id']}]"
                        f" has already been added")
        # if real_server_resp:
        data = resp.json()['data']
        return data

    def withdraw_relationship(self,
                            entity1_ilx: str,
                            relationship_ilx: str,
                            entity2_ilx: str) -> dict:
        """ Adds relationship connection in Interlex

        A relationship exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type relationship that connects entity1 to entity2
                -> Has its' own meta data, so no value needed
            3. entity with type term, cde, fde, or pde
        """
        entity1_data = self.get_entity(entity1_ilx)
        if not entity1_data['id']:
            raise self.EntityDoesNotExistError(f'entity1_ilx: {entity1_data} does not exist')
        relationship_data = self.get_entity(relationship_ilx)
        if not relationship_data['id']:
            raise self.EntityDoesNotExistError(f'relationship_ilx: {relationship_ilx} does not exist')
        entity2_data = self.get_entity(entity2_ilx)
        if not entity2_data['id']:
            raise self.EntityDoesNotExistError(f'entity2_ilx: {entity2_data} does not exist')
        data = {
            'term1_id': entity1_data['id'],  # entity1_data['id'],
            'relationship_tid': relationship_data['id'],  # relationship_data['id'],
            'term2_id': entity2_data['id'],  # entity2_data['id'],
            'term1_version': entity1_data['version'],
            'term2_version': entity2_data['version'],
            'relationship_term_version': relationship_data['version'],
            'withdrawn': '1',
            # 'orig_uid': self.user_id,  # BUG: php lacks orig_uid update
        }
        entity_relationships = self.get_relationship_via_tid(entity1_data['id'])
        # TODO: parse through entity_relationships to see if we have a match; else print warning and return None
        relationship_id = None
        for relationship in entity_relationships:
            if str(relationship['term1_id']) == str(entity1_data['id']):
                if str(relationship['term2_id']) == str(entity2_data['id']):
                    if str(relationship['relationship_tid']) == str(relationship_data['id']):
                        relationship_id = relationship['id']
                        break
        if not relationship_id:
            log.warning('Relationship you wanted to delete does not exist')
            return {}
        output = self._post(f'term/edit-relationship/{relationship_id}', 
                            data={**data, **{'batch-elastic': 'true'}}).json()['data']
        return output
