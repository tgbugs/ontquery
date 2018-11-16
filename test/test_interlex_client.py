import os
import pytest
import random
from ontquery.plugins.interlex_client import InterLexClient
from ontquery.plugins.services import InterLexRemote
import string


api_key = os.environ.get('INTERLEX_API_KEY', os.environ.get('SCICRUNCH_API_KEY', None))
ilxremote = InterLexRemote(
    api_key = api_key,
    apiEndpoint = 'https://beta.scicrunch.org/api/1/',
)
ilxremote.setup()
ilx_cli = ilxremote.ilx_cli


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


@pytest.mark.parametrize("test_input, expected", [
    ("ILX:123", 'ilx_123'),
    ("ilx_123", 'ilx_123'),
    ("TMP:123", 'tmp_123'),
    ("tmp_123", 'tmp_123'),
])
def test_fix_ilx(test_input, expected):
    assert ilx_cli.fix_ilx(test_input) == expected


def test_add_raw_entity():
    random_label = 'test_' + id_generator(size=12)

    entity = {
        'label': random_label,
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

    added_entity_data = ilx_cli.add_raw_entity(entity.copy())
    print(added_entity_data)
    # returned value is not identical to get_entity
    added_entity_data = ilx_cli.get_entity(added_entity_data['ilx'])
    print(added_entity_data)

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']
    assert added_entity_data['definition'] == entity['definition']
    assert added_entity_data['comment'] == entity['comment']
    assert added_entity_data['superclasses'][0]['ilx'] == entity['superclass']['ilx_id']
    assert added_entity_data['synonyms'][0]['literal'] == entity['synonyms'][0]['literal']
    assert added_entity_data['synonyms'][1]['literal'] == entity['synonyms'][1]['literal']
    assert added_entity_data['existing_ids'][0]['iri'] == entity['existing_ids'][0]['iri']
    assert added_entity_data['existing_ids'][0]['curie'] == entity['existing_ids'][0]['curie']

    ### ALREADY EXISTS TEST
    added_entity_data = ilx_cli.add_raw_entity(entity.copy())
    # returned value is not identical to get_entity
    added_entity_data = ilx_cli.get_entity(added_entity_data['ilx'])

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']
    assert added_entity_data['definition'] == entity['definition']
    assert added_entity_data['comment'] == entity['comment']
    assert added_entity_data['superclasses'][0]['ilx'] == entity['superclass']['ilx_id']
    assert added_entity_data['synonyms'][0]['literal'] == entity['synonyms'][0]['literal']
    assert added_entity_data['synonyms'][1]['literal'] == entity['synonyms'][1]['literal']
    assert added_entity_data['existing_ids'][0]['iri'] == entity['existing_ids'][0]['iri']
    assert added_entity_data['existing_ids'][0]['curie'] == entity['existing_ids'][0]['curie']

    # Invalid keys needed
    bad_entity = entity.copy()
    bad_entity.pop('label')
    with pytest.raises(
        ilx_cli.MissingKeyError,
        match=r"You need key\(s\): {'label'}"
    ):
        ilx_cli.add_raw_entity(bad_entity)

    # Invalid keys not wanted
    bad_entity = entity.copy()
    bad_entity['candy'] = 'snickers'
    with pytest.raises(
        ilx_cli.IncorrectKeyError,
        match=r"Unexpected key\(s\): {'candy'}"
    ):
        ilx_cli.add_raw_entity(bad_entity)

    # Invalid superclass ilx_id
    bad_entity = entity.copy()
    bad_entity['superclass']['ilx_id'] = 'ilx_rgb'
    with pytest.raises(
        ilx_cli.SuperClassDoesNotExistError,
        match=r"Superclass ILX ID: ilx_rgb does not exist in SciCrunch"
    ):
        ilx_cli.add_raw_entity(bad_entity)
    bad_entity = entity.copy()
    bad_entity['superclass']['ilx_id'] = 'ilx_0108124'

    # Invalid synonyms -> literal not found
    bad_entity['synonyms'][0]['literals'] = bad_entity['synonyms'][0].pop('literal')
    with pytest.raises(
        ValueError,
        match=r"Synonym not given a literal for label: " + bad_entity['label']
    ):
        ilx_cli.add_raw_entity(bad_entity)
    bad_entity['synonyms'][0]['literal'] = bad_entity['synonyms'][0].pop('literals')

    # Invalid synonyms -> keys besides literal found
    bad_entity = entity.copy()
    bad_entity['synonyms'][0]['literals'] = 'bad_literal_key'
    with pytest.raises(
        ValueError,
        match=r"Too many keys in synonym for label: " + bad_entity['label']
    ):
        ilx_cli.add_raw_entity(bad_entity)
    bad_entity['synonyms'][0].pop('literals')

    # Invalid existing_ids -> needed not found
    bad_entity = entity.copy()
    popped_iri = bad_entity['existing_ids'][0].pop('iri')
    with pytest.raises(
        ValueError,
        match=r"Missing needing key\(s\) in existing_ids for label: " + bad_entity['label']
    ):
        ilx_cli.add_raw_entity(bad_entity)
    bad_entity['existing_ids'][0]['iri'] = popped_iri

    # Invalid existing_ids -> needed not found
    bad_entity = entity.copy()
    bad_entity['existing_ids'][0]['iris'] = 'extra_key'
    with pytest.raises(
        ValueError,
        match=r"Extra keys not recognized in existing_ids for label: " + bad_entity['label']
    ):
        ilx_cli.add_raw_entity(bad_entity)
    bad_entity['existing_ids'][0].pop('iris')


def test_add_annotation():
    random_label = 'test_' + id_generator(size=12)
    entity = {
        'label': random_label,
        'type': 'annotation', # broken at the moment NEEDS PDE HARDCODED
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
    added_entity_data = ilx_cli.add_raw_entity(entity.copy())

    annotation = {
        'term_ilx_id': 'ilx_0101431', # brain ILX ID
        'annotation_type_ilx_id': added_entity_data['ilx'], # hasDbXref ILX ID
        'annotation_value': 'test_annotation_value',
    }

    added_anno_data = ilx_cli.add_annotation(**annotation.copy())
    assert added_anno_data['id'] != False
    assert added_anno_data['tid'] != False
    assert added_anno_data['annotation_tid'] != False
    assert added_anno_data['value'] == annotation['annotation_value']

    # MAKING SURE DUPLICATE STILL RETURNS SAME INFO
    added_anno_data = ilx_cli.add_annotation(**annotation.copy())
    assert added_anno_data['id'] != False
    assert added_anno_data['tid'] != False
    assert added_anno_data['annotation_tid'] != False
    assert added_anno_data['value'] == annotation['annotation_value']

    bad_anno = annotation.copy()
    bad_anno['term_ilx_id'] = 'ilx_rgb'
    with pytest.raises(
        SystemExit,
        match=r"term_ilx_id: ilx_rgb does not exist",
    ):
        ilx_cli.add_annotation(**bad_anno)

    bad_anno = annotation.copy()
    bad_anno['annotation_type_ilx_id'] = 'ilx_rgb'
    with pytest.raises(
        SystemExit,
        match=r"annotation_type_ilx_id: ilx_rgb does not exist",
    ):
        ilx_cli.add_annotation(**bad_anno)


def test_add_entity():
    random_label = 'test_' + id_generator(size=12)

    # TODO: commented out key/vals can be used for services test later
    entity = {
        'label': random_label,
        'type': 'term', # broken at the moment NEEDS PDE HARDCODED
        'definition': 'Part of the central nervous system',
        'comment': 'Cannot live without it',
        #'subThingOf': 'http://uri.interlex.org/base/ilx_0108124', # ILX ID for Organ
        'superclass': 'http://uri.interlex.org/base/ilx_0108124', # ILX ID for Organ
        'synonyms': ['Encephalon', 'Cerebro'],
        # 'predicates': {
        #     'http://uri.interlex.org/base/tmp_0381624': 'sample_value' # hasDbXref beta ID
        # }
    }
    added_entity_data = ilx_cli.add_entity(**entity.copy())

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']
    assert added_entity_data['definition'] == entity['definition']
    assert added_entity_data['comment'] == entity['comment']
    #assert added_entity_data['superclasses'][0]['ilx'] == entity['subThingOf'].replace('http://uri.interlex.org/base/', '')
    assert added_entity_data['superclass'] == entity['superclass']
    assert added_entity_data['synonyms'][0] == entity['synonyms'][0]
    assert added_entity_data['synonyms'][1] == entity['synonyms'][1]

    ### ALREADY EXISTS TEST
    added_entity_data = ilx_cli.add_entity(**entity.copy())

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']
    assert added_entity_data['definition'] == entity['definition']
    assert added_entity_data['comment'] == entity['comment']
    #assert added_entity_data['superclasses'][0]['ilx'] == entity['subThingOf'].replace('http://uri.interlex.org/base/', '')
    assert added_entity_data['superclass'] == entity['superclass']
    assert added_entity_data['synonyms'][0] == entity['synonyms'][0]
    assert added_entity_data['synonyms'][1] == entity['synonyms'][1]

def test_add_entity_minimum():
    random_label = 'test_' + id_generator(size=12)

    # TODO: commented out key/vals can be used for services test later
    entity = {
        'label': random_label,
        'type': 'term', # broken at the moment NEEDS PDE HARDCODED
    }
    added_entity_data = ilx_cli.add_entity(**entity.copy())

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']

    ### ALREADY EXISTS TEST
    added_entity_data = ilx_cli.add_entity(**entity.copy())

    assert added_entity_data['label'] == entity['label']
    assert added_entity_data['type'] == entity['type']
