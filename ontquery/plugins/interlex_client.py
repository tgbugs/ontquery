import json
import os
import requests
from sys import exit
from typing import List


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

    def __init__(self, api_key: str, base_url: str = 'https://scicrunch.org'):
        self.api_key = api_key
        self.base_url = base_url
        self.user_id = self.get(
            url = 'https://scicrunch.org/api/1/user/info?key=' + self.api_key
        )['id']

    def process_response(self, response: requests.models.Response) -> dict:
        """ Checks for correct data response and status codes """
        try:
            output = response.json()
        except: # Server is having a bad day and crashed.
            exit(
                'Json not returned with status code [' + str(response.status_code) + ']'
            )

        if response.status_code == 400:
            return output

        if response.status_code not in [200, 201]: # Safety catch.
            exit(
                str(output) + ': with status code [' + str(response.status_code) +
                '] and params:' + str(output)
            )

        return output['data']

    def get(self, url: str) -> List[dict]:
        """ Requests data from database """
        response = requests.get(
            url,
            headers = {'Content-type': 'application/json'},
            auth = ('scicrunch', 'perl22(query)') # for test2.scicrunch.org
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
            auth = ('scicrunch', 'perl22(query)') # for test2.scicrunch.org
        )
        output = self.process_response(response)
        return output

    def fix_ilx(self, ilx_id: str) -> str:
        """ Database only excepts lower case and underscore version of ID """
        ilx_id = ilx_id.replace('http://uri.interlex.org/base/', '')
        if ilx_id[:4] not in ['TMP:', 'tmp_', 'ILX:', 'ilx_']:
            exit(
                'Need to provide ilx ID with format ilx_# or ILX:# for given ID ' + ilx_id
            )
        return ilx_id.replace('ILX:', 'ilx_').replace('TMP:', 'tmp_')

    def process_superclass(self, entity: List[dict]) -> List[dict]:
        """ Replaces ILX ID with superclass ID """
        superclass = entity.pop('superclass')
        label = entity['label']
        if not superclass.get('ilx_id'):
            exit(
                'Superclass not given an interlex ID for label: ' + label
            )
        superclass_data = self.get_entity(superclass['ilx_id'])
        if not superclass_data['id']:
            exit(
                'Superclass ILX ID: ' + superclass['ilx_id'] + ' does not exist in SciCrunch'
            )
        # BUG: only excepts superclass_tid
        entity['superclasses'] = [{'superclass_tid': superclass_data['id']}]
        return entity

    def process_synonyms(self, entity: List[dict]) -> List[dict]:
        """ Making sure key/value is in proper format for synonyms in entity """
        label = entity['label']
        for synonym in entity['synonyms']:
            if not synonym.get('literal'):
                exit(
                    'Synonym not given a literal for label: ' + label
                )
            elif set(synonym) | set(['literal']) != set(['literal']):
                exit(
                    'Extra key(s) not recognized in synonyms for label: ' + label
                )
        return entity

    def process_existing_ids(self, entity: List[dict]) -> List[dict]:
        """ Making sure key/value is in proper format for existing_ids in entity """
        label = entity['label']
        existing_ids = entity['existing_ids']
        for existing_id in existing_ids:
            if set(existing_id) & set(['iri', 'curie']) != set(['iri', 'curie']):
                exit(
                    'Missing needing key(s) in existing_ids for label: ' + label
                )
            elif set(existing_id) | set(['iri', 'curie']) != set(['iri', 'curie']):
                exit(
                    'Extra keys not recognized in existing_ids for label: ' + label
                )
        return entity

    def crude_search_scicrunch_via_label(self, label:str) -> dict:
        """ Server returns anything that is simlar in any catagory """
        url = self.base_url + '/api/1/term/search/{term}?key={api_key}'.format(
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
        url = self.base_url + "/api/1/ilx/search/identifier/{identifier}?key={api_key}".format(
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
        synonyms: list = None,
    ) -> List[dict]:

        if not label:
            exit('Entity needs a label')
        if not type:
            exit('Entity needs a type')

        entity = {
            'label': label,
            'type': type,
        }

        if definition:
            entity['definition'] = definition

        if comment:
            entity['comment'] = comment

        if superclass:
            entity['superclass'] = {'ilx_id':self.fix_ilx(superclass)}

        if synonyms:
            entity['synonyms'] = [{'literal': syn} for syn in synonyms]

        return self.add_raw_entity(entity)

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
        prime_entity_url = self.base_url + '/api/1/ilx/add'
        add_entity_url = self.base_url + '/api/1/term/add'

        ### Checking if key/value format is currect ###
        # Seeing if you are missing a needed key
        if (set(entity) & needed_in_entity) != needed_in_entity:
            exit(
                'You need key(s): '+ str(needed_in_entity - set(entity))
            )
        # Seeing if you have other options not included in the description
        elif (set(entity) | options_in_entity) != options_in_entity:
            exit(
                'Unexpected key(s): ' + str(set(entity) - options_in_entity)
            )
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
                    print(
                        'You already added entity', entity['label'],
                        'with ILX ID:', prexisting_data['ilx']
                    )
                    return prexisting_data
                exit(output)
            exit(output)

        output['superclasses'][0].pop('dbObj') # BUG: bad data
        return output

    def get_annotation_via_tid(self, tid: str) -> dict:
        """ Gets annotation via anchored entity id """
        url = self.base_url + '/api/1/term/get-annotations/{tid}?key={api_key}'.format(
            tid = tid,
            api_key = self.api_key,
        )
        return self.get(url)

    def add_annotation(
        self,
        term_ilx_id: str,
        annotation_type_ilx_id: str,
        annotation_value: str,
    ) -> dict:
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
        url = self.base_url + '/api/1/term/add-annotation'

        term_data = self.get_entity(term_ilx_id)
        if not term_data['id']:
            exit(
                'term_ilx_id: ' + term_ilx_id + ' does not exist'
            )
        anno_data = self.get_entity(annotation_type_ilx_id)
        if not anno_data['id']:
            exit(
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
                            print(
                                'Annotation: [' + term_data['label'] + ' -> ' + anno_data['label'] +
                                ' -> ' + data['value'] + '], already exists.'
                            )
                            return term_annotation
            exit(output)

        return output

def example():
    sci = InterLexClient(
        api_key = os.environ.get('INTERLEX_API_KEY'),
        base_url = 'https://beta.scicrunch.org',
    )
    entity = {
        'label': 'brain103',
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
    annotation = {
        'term_ilx_id': 'ilx_0101431', # brain ILX ID
        'annotation_type_ilx_id': 'tmp_0381624', # hasDbXref ILX ID
        'annotation_value': 'PMID:12345',
    }
    print(sci.add_raw_entity(entity))
    print(sci.add_annotation(**annotation))

if __name__ == '__main__':
    example()
