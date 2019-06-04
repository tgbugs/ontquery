import json
import os
import requests
from typing import List, Tuple
from ontquery.utils import log


class InterLexClient:

    """ Connects to SciCrunch via its' api endpoints

    Purpose is to allow external curators to add entities and annotations to those entities.

    Functions To Use:
        add_entity
        add_annotation

    Notes On Time Complexity:
        Function add_entity, if added an entity successfully, will hit a least 5 endpoints. This
        may cause it to take a few seconds to load each entity into SciCrunch. Function
        add_annotation is a little more forgiving with it only hitting 3 minimum.
    """

    class Error(Exception): pass

    class SuperClassDoesNotExistError(Error):
        """ The superclass listed does not exist! """

    class EntityDoesNotExistError(Error):
        """ The entity listed does not exist! """

    class AlreadyExistsError(Error):
        """ The entity listed already exists! """

    class BadResponseError(Error): pass

    class NoLabelError(Error): pass

    class NoTypeError(Error): pass

    class MissingKeyError(Error): pass

    class IncorrectKeyError(Error): pass

    class IncorrectAPIKeyError(Error): pass

    default_base_url = 'https://scicrunch.org/api/1/'
    ilx_base_url = 'http://uri.interlex.org/base/'

    def __init__(self, base_url: str=default_base_url):
        self.base_url = base_url
        self.api_key = os.environ.get('INTERLEX_API_KEY', os.environ.get('SCICRUNCH_API_KEY', None))
        self._kwargs = {}
        if 'test' in base_url:
            auth = os.environ['SCICRUNCH_TEST_U'], os.environ['SCICRUNCH_TEST_P']
            self._kwargs['auth'] = auth

        user_info_url = self.default_base_url + 'user/info?key=' + self.api_key
        self.check_api_key(user_info_url)
        self.user_id = str(self.get(user_info_url)['id'])
    def check_api_key(self, url):
        response = requests.get(
            url,
            headers = {'Content-type': 'application/json'},
            **self._kwargs
        )
        if response.status_code not in [200, 201]: # Safety catch.
            sec = url.replace(self.api_key, '[secure]')
            raise self.IncorrectAPIKeyError(f'api_key given is incorrect. {sec}')

    def process_response(self, response: requests.models.Response) -> dict:
        """ Checks for correct data response and status codes """
        try:
            output = response.json()
        except json.JSONDecodeError: # Server is having a bad day and crashed.
            raise self.BadResponseError(
                'Json not returned with status code [' + str(response.status_code) + ']')

        if response.status_code == 400:
            return output

        if response.status_code not in [200, 201]: # Safety catch.
            raise self.BadResponseError(
                str(output) + ': with status code [' + str(response.status_code) +
                '] and params:' + str(output))

        return output['data']

    def get(self, url: str) -> List[dict]:
        """ Requests data from database """
        response = requests.get(
            url,
            headers = {'Content-type': 'application/json'},
            **self._kwargs
        )
        output = self.process_response(response)
        return output

    def post(self, url: str, data: List[dict]) -> List[dict]:
        """ Gives data to database """
        data.update({
            'key': self.api_key,
        })
        response = requests.post(
            url,
            data = json.dumps(data),
            headers = {'Content-type': 'application/json'},
            **self._kwargs
        )
        output = self.process_response(response)
        return output

    def fix_ilx(self, ilx_id: str) -> str:
        """ Database only excepts lower case and underscore version of ID """
        # FIXME probably .rsplit('/', 1) is the more correct version of this
        # and because this is nominally a 'private' interface these should be
        ilx_id = ilx_id.replace('http://uri.interlex.org/base/', '')
        if ilx_id[:4] not in ['TMP:', 'tmp_', 'ILX:', 'ilx_']:
            raise ValueError(
                'Need to provide ilx ID with format ilx_# or ILX:# for given ID ' + ilx_id)
        return ilx_id.replace('ILX:', 'ilx_').replace('TMP:', 'tmp_')

    def process_superclass(self, entity: List[dict]) -> List[dict]:
        """ Replaces ILX ID with superclass ID """
        superclass = entity.pop('superclass')
        label = entity['label']
        if not superclass.get('ilx_id'):
            raise self.SuperClassDoesNotExistError(
                f'Superclass not given an interlex ID for label: {label}')
        superclass_data = self.get_entity(superclass['ilx_id'])
        if not superclass_data['id']:
            raise self.SuperClassDoesNotExistError(
                'Superclass ILX ID: ' + superclass['ilx_id'] + ' does not exist in SciCrunch')
        # BUG: only excepts superclass_tid
        entity['superclasses'] = [{'superclass_tid': superclass_data['id']}]
        return entity

    def process_synonyms(self, entity: List[dict]) -> List[dict]:
        """ Making sure key/value is in proper format for synonyms in entity """
        label = entity['label']
        for synonym in entity['synonyms']:
            # these are internal errors and users should never see them
            if 'literal' not in synonym:
                raise ValueError(f'Synonym not given a literal for label: {label}')
            elif len(synonym) > 1:
                raise ValueError(f'Too many keys in synonym for label: {label}')
        return entity

    def process_existing_ids(self, entity: List[dict]) -> List[dict]:
        """ Making sure key/value is in proper format for existing_ids in entity """
        label = entity['label']
        existing_ids = entity['existing_ids']
        for existing_id in existing_ids:
            if 'curie' not in existing_id or 'iri' not in existing_id:
                raise ValueError(
                    f'Missing needing key(s) in existing_ids for label: {label}')
            elif len(existing_id) > 2:
                raise ValueError(
                    f'Extra keys not recognized in existing_ids for label: {label}')
        return entity

    def crude_search_scicrunch_via_label(self, label:str) -> dict:
        """ Server returns anything that is simlar in any catagory """
        url = self.base_url + 'term/search/{term}?key={api_key}'.format(
            term = label,
            api_key = self.api_key,
        )
        return self.get(url)

    def check_scicrunch_for_label(self, label: str) -> dict:
        """ Sees if label with your user ID already exists

        There are can be multiples of the same label in interlex, but there should only be one
        label with your user id. Therefore you can create labels if there already techniqually
        exist, but not if you are the one to create it.
        """
        list_of_crude_matches = self.crude_search_scicrunch_via_label(label)
        for crude_match in list_of_crude_matches:
            # If labels match
            if crude_match['label'].lower().strip() == label.lower().strip():
                complete_data_of_crude_match = self.get_entity(crude_match['ilx'])
                crude_match_label = crude_match['label']
                crude_match_user_id = complete_data_of_crude_match['uid']
                # If label was created by you
                if str(self.user_id) == str(crude_match_user_id):
                    return complete_data_of_crude_match # You created the entity already
        # No label AND user id match
        return {}

    def get_entity(self, ilx_id: str) -> dict:
        """ Gets full meta data (expect their annotations and relationships) from is ILX ID """
        ilx_id = self.fix_ilx(ilx_id)
        url = self.base_url + "ilx/search/identifier/{identifier}?key={api_key}".format(
            identifier = ilx_id,
            api_key = self.api_key,
        )
        return self.get(url)

    def add_entity(
        self,
        label: str,
        type: str,
        definition: str = None,
        comment: str = None,
        superclass: str = None,
        synonyms: list = None) -> dict:

        template_entity_input = {k:v for k, v in locals().items() if k != 'self' and v}
        if template_entity_input.get('superclass'):
            template_entity_input['superclass'] = self.fix_ilx(template_entity_input['superclass'])

        if not label:
            raise self.NoLabelError('Entity needs a label')
        if not type:
            raise self.NoTypeError('Entity needs a type')

        entity_input = {
            'label': label,
            'type': type,
        }

        if definition:
            entity_input['definition'] = definition

        if comment:
            entity_input['comment'] = comment

        if superclass:
            entity_input['superclass'] = {'ilx_id':self.fix_ilx(superclass)}

        if synonyms:
            entity_input['synonyms'] = [{'literal': syn} for syn in synonyms]

        raw_entity_outout = self.add_raw_entity(entity_input)

        # Sanity check -> output same as input, but filled with response data
        entity_output = {}
        ics = [(e['iri'], e['curie'])
               for e in raw_entity_outout['existing_ids']]
        entity_output['iri'], entity_output['curie'] = sorted((i, c)
                                                              for i, c in ics
                                                              if 'ilx_' in i)[0]
        ### FOR NEW BETA. Old can have 'ilx_' in the ids ###
        if 'tmp' in raw_entity_outout['ilx']:
            _id = raw_entity_outout['ilx'].split('_')[-1]
            entity_output['iri'] = 'http://uri.interlex.org/base/tmp_' + _id
            entity_output['curie'] = 'TMP:' + _id

        for key, value in template_entity_input.items():
            if key == 'superclass':
                entity_output[key] = raw_entity_outout['superclasses'][0]['ilx']
            elif key == 'synonyms':
                entity_output[key] = [syn['literal']
                                      for syn in raw_entity_outout['synonyms']]
            else:
                entity_output[key] = str(raw_entity_outout[key])

        # skip this for now, I check it downstream be cause I'm paranoid, but in this client it is
        # safe to assume that the value given will be the value returned if there is a return at all
        # it also isn't that they match exactly, because some new values (e.g. iri and curie) are expected
        #if entity_output != template_entity_input:
            # DEBUG: helps see what's wrong; might want to make a clean version of this
            # for key, value in template_entity_input.items():
            #     if template_entity_input[key] != entity_output[key]:
            #         print(template_entity_input[key], entity_output[key])
            #raise self.BadResponseError('The server did not return proper data!')

        if entity_output.get('superclass'):
            entity_output['superclass'] = self.ilx_base_url + entity_output['superclass']
        entity_output['ilx'] = self.ilx_base_url + raw_entity_outout['ilx']

        return entity_output

    def add_raw_entity(self, entity: dict) -> dict:
        """ Adds entity if it does not already exist under your user ID.

            Need to provide a list of dictionaries that have at least the key/values
            for label and type. If given a key, the values provided must be in the
            format shown in order for the server to except them. You can input
            multiple synonyms, or existing_ids.

            Entity type can be any of the following: term, pde, fde, cde, annotation, or relationship

            Options Template:
                entity = {
                    'label': '',
                    'type': '',
                    'definition': '',
                    'comment': '',
                    'superclass': {
                        'ilx_id': ''
                    },
                    'synonyms': [
                        {
                            'literal': ''
                        },
                    ],
                    'existing_ids': [
                        {
                            'iri': '',
                            'curie': '',
                        },
                    ],
                }

            Minimum Needed:
                entity = {
                    'label': '',
                    'type': '',
                }

            Example:
                entity = {
                    'label': 'brain',
                    'type': 'pde',
                    'definition': 'Part of the central nervous system',
                    'comment': 'Cannot live without it',
                    'superclass': {
                        'ilx_id': 'ilx_0108124', # ILX ID for Organ
                    },
                    'synonyms': [
                        {
                            'literal': 'Encephalon'
                        },
                        {
                            'literal': 'Cerebro'
                        },
                    ],
                    'existing_ids': [
                        {
                            'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_796',
                            'curie': 'BIRNLEX:796',
                        },
                    ],
                }
        """

        needed_in_entity = set([
            'label',
            'type',
        ])
        options_in_entity = set([
            'label',
            'type',
            'definition',
            'comment',
            'superclass',
            'synonyms',
            'existing_ids'
        ])
        prime_entity_url = self.base_url + 'ilx/add'
        add_entity_url = self.base_url + 'term/add'

        ### Checking if key/value format is correct ###
        # Seeing if you are missing a needed key
        if (set(entity) & needed_in_entity) != needed_in_entity:
            raise self.MissingKeyError(
                'You need key(s): '+ str(needed_in_entity - set(entity)))
        # Seeing if you have other options not included in the description
        elif (set(entity) | options_in_entity) != options_in_entity:
            raise self.IncorrectKeyError(
                'Unexpected key(s): ' + str(set(entity) - options_in_entity))
        entity['type'] = entity['type'].lower() # BUG: server only takes lowercase
        if entity['type'] not in ['term', 'relationship', 'annotation', 'cde', 'fde', 'pde']:
            raise TypeError(
                'Entity should be one of the following: ' +
                'term, relationship, annotation, cde, fde, pde')
        if entity.get('superclass'):
            entity = self.process_superclass(entity)
        if entity.get('synonyms'):
            entity = self.process_synonyms(entity)
        if entity.get('existing_ids'):
            entity = self.process_existing_ids(entity)
        entity['uid'] = self.user_id # BUG: php lacks uid update

        ### Adding entity to SciCrunch ###
        entity['term'] = entity.pop('label') # ilx/add nuance
        ilx_data = self.post(
            url = prime_entity_url,
            data = entity.copy(),
        ) # requesting spot in server for entity
        if ilx_data.get('ilx'):
            ilx_id = ilx_data['ilx']
        else:
            ilx_id = ilx_data['fragment'] # beta.scicrunch.org
        entity['label'] = entity.pop('term') # term/add nuance
        entity['ilx'] = ilx_id # need entity ilx_id to place entity in db

        output = self.post(
            url = add_entity_url,
            data = entity.copy(),
        ) # data represented in SciCrunch interface

        ### Checking if label already exisits ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                prexisting_data = self.check_scicrunch_for_label(entity['label'])
                if prexisting_data:
                    log.warning(
                        'You already added entity ' + entity['label'],
                        'with ILX ID: ' + prexisting_data['ilx'])

                    return prexisting_data

                self.Error(output)  # FIXME what is the correct error here?

            self.Error(output)  # FIXME what is the correct error here?

        # BUG: server output incomplete compared to search via ilx ids
        output = self.get_entity(output['ilx'])

        return output

    def update_entity(
        self,
        ilx_id: str,
        label: str = None,
        type: str = None,
        definition: str = None,
        comment: str = None,
        superclass: str = None,
        synonyms: list = None) -> dict:
        """ Updates pre-existing entity as long as the api_key is from the account that created it

            Args:
                label: name of entity
                type: entities type
                    Can be any of the following: term, cde, fde, pde, annotation, relationship
                definition: entities definition
                comment: a foot note regarding either the interpretation of the data or the data itself
                superclass: entity is a sub-part of this entity
                    Example: Organ is a superclass to Brain
                synonyms: entity synonyms

            Returns:
                Server response that is a nested dictionary format
        """

        template_entity_input = {k:v for k, v in locals().copy().items() if k != 'self'}
        if template_entity_input.get('superclass'):
            template_entity_input['superclass'] = self.fix_ilx(template_entity_input['superclass'])

        existing_entity = self.get_entity(ilx_id=ilx_id)
        if not existing_entity['id']: # TODO: Need to make a proper ilx_id check error
            raise self.EntityDoesNotExistError(
                f'ilx_id provided {ilx_id} does not exist')

        update_url = self.base_url + 'term/edit/{id}'.format(id=existing_entity['id'])

        if label:
            existing_entity['label'] = label

        if type:
            existing_entity['type'] = type

        if definition:
            existing_entity['definition'] = definition

        if comment:
            existing_entity['comment'] = comment

        if superclass:
            existing_entity['superclass'] = {'ilx_id': superclass}
            existing_entity = self.process_superclass(existing_entity)

        # If a match use old data, else append new synonym
        if synonyms:
            if existing_entity['synonyms']:
                new_existing_synonyms = []
                existing_synonyms = {syn['literal'].lower():syn for syn in existing_entity['synonyms']}
                for synonym in synonyms:
                    existing_synonym = existing_synonyms.get(synonym.lower())
                    if not existing_synonym:
                        new_existing_synonyms.append({'literal': synonym})
                    else:
                        new_existing_synonyms.append(existing_synonym)
                existing_entity['synonyms'] = new_existing_synonyms

        # Just in case I need this...
        # if synonyms_to_delete:
        #     if existing_entity['synonyms']:
        #         remaining_existing_synonyms = []
        #         existing_synonyms = {syn['literal'].lower():syn for syn in existing_entity['synonyms']}
        #         for synonym in synonyms:
        #             if existing_synonyms.get(synonym.lower()):
        #                 existing_synonyms.pop(synonym.lower())
        #             else:
        #                 print('WARNING: synonym you wanted to delete', synonym, 'does not exist')
        #         existing_entity['synonyms'] = list(existing_synonyms.values())

        response = self.post(
            url = update_url,
            data = existing_entity,
        )

        # BUG: server response is bad and needs to actually search again to get proper format
        raw_entity_outout = self.get_entity(response['ilx'])

        entity_output = {}
        ics = [(e['iri'], e['curie'])
               for e in raw_entity_outout['existing_ids']]
        entity_output['iri'], entity_output['curie'] = sorted((i, c)
                                                    for i, c in ics
                                                    if 'ilx_' in i)[0]
        ### FOR NEW BETA. Old can have 'ilx_' in the ids ###
        if 'tmp' in raw_entity_outout['ilx']:
            _id = raw_entity_outout['ilx'].split('_')[-1]
            entity_output['iri'] = 'http://uri.interlex.org/base/tmp_' + _id
            entity_output['curie'] = 'TMP:' + _id

        log.info(template_entity_input)
        for key, value in template_entity_input.items():
            if key == 'superclass':
                if raw_entity_outout.get('superclasses'):
                    entity_output[key] = raw_entity_outout['superclasses'][0]['ilx']
            elif key == 'synonyms':
                entity_output[key] = [syn['literal']
                                      for syn in raw_entity_outout['synonyms']]
            elif key == 'ilx_id':
                pass
            else:
                entity_output[key] = str(raw_entity_outout[key])

        if entity_output.get('superclass'):
            entity_output['superclass'] = self.ilx_base_url + entity_output['superclass']
        entity_output['ilx'] = self.ilx_base_url + raw_entity_outout['ilx']

        return entity_output

    def get_annotation_via_tid(self, tid: str) -> dict:
        """ Gets annotation via anchored entity id """
        url = self.base_url + 'term/get-annotations/{tid}?key={api_key}'.format(
            tid = tid,
            api_key = self.api_key,
        )
        return self.get(url)

    def add_annotation(
        self,
        term_ilx_id: str,
        annotation_type_ilx_id: str,
        annotation_value: str) -> dict:
        """ Adding an annotation value to a prexisting entity

        An annotation exists as 3 different parts:
            1. entity with type term, cde, fde, or pde
            2. entity with type annotation
            3. string value of the annotation

        Example:
            annotation = {
                'term_ilx_id': 'ilx_0101431', # brain ILX ID
                'annotation_type_ilx_id': 'ilx_0381360', # hasDbXref ILX ID
                'annotation_value': 'http://neurolex.org/wiki/birnlex_796',
            }
        """
        url = self.base_url + 'term/add-annotation'

        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            raise self.EntityDoesNotExistError(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            raise self.EntityDoesNotExistError(
                'annotation_type_ilx_id: ' + annotation_type_ilx_id +
                ' does not exist'
            )

        data = {
            'tid': term_data['id'],
            'annotation_tid': anno_data['id'],
            'value': annotation_value,
            'term_version': term_data['version'],
            'annotation_term_version': anno_data['version'],
            'orig_uid': self.user_id, # BUG: php lacks orig_uid update
        }

        output = self.post(
            url = url,
            data = data,
        )

        ### If already exists, we return the actual annotation properly ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                term_annotations = self.get_annotation_via_tid(term_data['id'])
                for term_annotation in term_annotations:
                    if str(term_annotation['annotation_tid']) == str(anno_data['id']):
                        if term_annotation['value'] == data['value']:
                            log.warning(
                                'Annotation: [' + term_data['label'] + ' -> ' + anno_data['label'] +
                                ' -> ' + data['value'] + '], already exists.'
                            )
                            return term_annotation

                raise self.AlreadyExistsError(output)

            raise self.Error(output)

        return output

    def delete_annotation(
        self,
        term_ilx_id: str,
        annotation_type_ilx_id: str,
        annotation_value: str) -> dict:
        """ If annotation doesnt exist, add it
        """

        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            raise self.EntityDoesNotExistError(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            raise self.EntityDoesNotExistError(
                'annotation_type_ilx_id: ' + annotation_type_ilx_id +
                ' does not exist'
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

        url = self.base_url + 'term/edit-annotation/{annotation_id}'.format(
            annotation_id = annotation_id
        )

        data = {
            'tid': ' ', # for delete
            'annotation_tid': ' ', # for delete
            'value': ' ', # for delete
            'term_version': ' ',
            'annotation_term_version': ' ',
        }

        output = self.post(
            url = url,
            data = data,
        )

        # check output
        return output

    def get_relationship_via_tid(self, tid: str) -> dict:
        url = self.base_url + 'term/get-relationships/{tid}?key={api_key}'.format(
            tid = tid,
            api_key = self.api_key,
        )
        return self.get(url)

    def add_relationship(
        self,
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

        url = self.base_url + 'term/add-relationship'

        entity1_data = self.get_entity(entity1_ilx)
        if not entity1_data['id']:
            raise self.EntityDoesNotExistError(
                'entity1_ilx: ' + entity1_ilx + ' does not exist'
            )
        relationship_data = self.get_entity(relationship_ilx)
        if not relationship_data['id']:
            raise self.EntityDoesNotExistError(
                'relationship_ilx: ' + relationship_ilx + ' does not exist'
            )
        entity2_data = self.get_entity(entity2_ilx)
        if not entity2_data['id']:
            raise self.EntityDoesNotExistError(
                'entity2_ilx: ' + entity2_ilx + ' does not exist'
            )

        data = {
            'term1_id': entity1_data['id'],
            'relationship_tid': relationship_data['id'],
            'term2_id': entity2_data['id'],
            'term1_version': entity1_data['version'],
            'term2_version': entity2_data['version'],
            'relationship_term_version': relationship_data['version'],
            'orig_uid': self.user_id, # BUG: php lacks orig_uid update
        }

        output = self.post(
            url = url,
            data = data,
        )
        ### If already exists, we return the actual relationship properly ###
        if output.get('errormsg'):
            if 'already exists' in output['errormsg'].lower():
                term_relationships = self.get_relationship_via_tid(entity1_data['id'])
                for term_relationship in term_relationships:
                    if str(term_relationship['term2_id']) == str(entity2_data['id']):
                        if term_relationship['relationship_tid'] == relationship_data['id']:
                            log.warning(
                                'relationship: [' + entity1_data['label'] + ' -> ' +
                                relationship_data['label'] + ' -> ' + entity2_data['label'] +
                                '], already exists.'
                            )
                            return term_relationship
                exit(output)
            exit(output)

        return output

    def delete_relationship(
        self,
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
            raise self.EntityDoesNotExistError(
                'entity1_ilx: ' + entity1_data + ' does not exist'
            )
        relationship_data = self.get_entity(relationship_ilx)
        if not relationship_data['id']:
            raise self.EntityDoesNotExistError(
                'relationship_ilx: ' + relationship_ilx + ' does not exist'
            )
        entity2_data = self.get_entity(entity2_ilx)
        if not entity2_data['id']:
            raise self.EntityDoesNotExistError(
                'entity2_ilx: ' + entity2_data + ' does not exist'
            )

        data = {
            'term1_id': ' ', #entity1_data['id'],
            'relationship_tid': ' ', #relationship_data['id'],
            'term2_id': ' ',#entity2_data['id'],
            'term1_version': entity1_data['version'],
            'term2_version': entity2_data['version'],
            'relationship_term_version': relationship_data['version'],
            'orig_uid': self.user_id, # BUG: php lacks orig_uid update
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
            log.warning('Annotation you wanted to delete does not exist')
            return {}

        url = self.base_url + 'term/edit-relationship/{id}'.format(id=relationship_id)

        output = self.post(
            url = url,
            data = data,
        )

        return output

def examples():
    ''' Examples of how to use. Default are that some functions are commented out in order
        to not cause harm to existing metadata within the database.
    '''
    sci = InterLexClient(
        api_key = os.environ.get('INTERLEX_API_KEY'),
        base_url = 'https://test.scicrunch.org/api/1/', # NEVER CHANGE
    )
    entity = {
        'label': 'brain115',
        'type': 'fde', # broken at the moment NEEDS PDE HARDCODED
        'definition': 'Part of the central nervous system',
        'comment': 'Cannot live without it',
        'superclass': {
            'ilx_id': 'ilx_0108124', # ILX ID for Organ
        },
        'synonyms': [
            {
                'literal': 'Encephalon'
            },
            {
                'literal': 'Cerebro'
            },
        ],
        'existing_ids': [
            {
                'iri': 'http://uri.neuinfo.org/nif/nifstd/birnlex_796',
                'curie': 'BIRNLEX:796',
            },
        ],
    }
    simple_entity = {
        'label': entity['label'],
        'type': entity['type'], # broken at the moment NEEDS PDE HARDCODED
        'definition': entity['definition'],
        'comment': entity['comment'],
        'superclass': entity['superclass']['ilx_id'],
        'synonyms': [syn['literal'] for syn in entity['synonyms']],
        'predicates': {'tmp_0381624': 'http://example_dbxref'}
    }
    annotation = {
        'term_ilx_id': 'ilx_0101431', # brain ILX ID
        'annotation_type_ilx_id': 'tmp_0381624', # hasDbXref ILX ID
        'annotation_value': 'PMID:12345',
    }
    relationship = {
        'entity1_ilx': 'ilx_0101431', # brain
        'relationship_ilx': 'ilx_0115023', # Related to
        'entity2_ilx': 'ilx_0108124', #organ
    }
    update_entity_data = {
        'ilx_id': 'ilx_0101431',
        'label': 'Brain',
        'definition': 'update_test!!',
        'type': 'fde',
        'comment': 'test comment',
        'superclass': 'ilx_0108124',
        'synonyms': ['test', 'test2', 'test2'],
    }
    # resp = sci.delete_annotation(**{
    #     'term_ilx_id': 'ilx_0101431', # brain ILX ID
    #     'annotation_type_ilx_id': 'ilx_0115071', # hasConstraint ILX ID
    #     'annotation_value': 'test_12345',
    # })
    relationship = {
        'entity1_ilx': 'http://uri.interlex.org/base/ilx_0100001', # (R)N6 chemical ILX ID
        'relationship_ilx': 'http://uri.interlex.org/base/ilx_0112772', # Afferent projection ILX ID
        'entity2_ilx': 'http://uri.interlex.org/base/ilx_0100000', #1,2-Dibromo chemical ILX ID
    }
    # print(sci.add_relationship(**relationship))
    # print(resp)
    # print(sci.update_entity(**update_entity_data))
    # print(sci.add_raw_entity(entity))
    # print(sci.add_entity(**simple_entity))
    # print(sci.add_annotation(**annotation))
    # print(sci.add_relationship(**relationship))

if __name__ == '__main__':
    examples()
