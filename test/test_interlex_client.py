import os
import pytest
import random
from ontquery.plugins.interlex_client import InterLexClient
from ontquery.plugins.services import InterLexRemote
import ontquery as oq
import string

def test_api_key():
    ilxremote = InterLexRemote(apiEndpoint='https://test.scicrunch.org/api/1/')
    ilxremote.setup(instrumented=oq.OntTerm)
    ilx_cli = ilxremote.ilx_cli
    assert ilx_cli.api_key == ilxremote.api_key
    os.environ['INTERLEX_API_KEY'] = 'fake_key_12345'  # shadows the scicrunch key in tests
    with pytest.raises(ilx_cli.IncorrectAPIKeyError,
                       match = "api_key given is incorrect."):
        ilxremote = InterLexRemote(apiEndpoint='https://test.scicrunch.org/api/1/')
        ilxremote.setup(instrumented=oq.OntTerm)

    os.environ.pop('INTERLEX_API_KEY')  # unshadow
    assert not os.environ.get('INTERLEX_API_KEY')


ilxremote = InterLexRemote(apiEndpoint='https://test.scicrunch.org/api/1/')
ilxremote.setup(instrumented=oq.OntTerm)
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
            'ilx_id': 'tmp_0108124', # ILX ID for Organ
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
    bad_entity['superclass']['ilx_id'] = 'tmp_0108124'

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
            'ilx_id': 'tmp_0108124', # ILX ID for Organ
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
        'term_ilx_id': 'tmp_0101431', # brain ILX ID
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
        ilx_cli.EntityDoesNotExistError,
        match=r"term_ilx_id: ilx_rgb does not exist",
    ):
        ilx_cli.add_annotation(**bad_anno)

    bad_anno = annotation.copy()
    bad_anno['annotation_type_ilx_id'] = 'ilx_rgb'
    with pytest.raises(
        ilx_cli.EntityDoesNotExistError,
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
        'superclass': 'http://uri.interlex.org/base/tmp_0108124', # ILX ID for Organ
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


def test_update_entity():

    def rando_str():
        return 'test_' + id_generator(size=12)

    label = 'Brain'
    type = 'fde'
    superclass = 'tmp_0108124'
    definition = rando_str()
    comment = rando_str()
    synonym = rando_str()

    update_entity_data = {
        'ilx_id': 'tmp_0101431',
        'label': label,
        'definition': definition,
        'type': type,
        'comment': comment,
        'superclass': superclass,
        'synonyms': ['test', synonym],
    }

    updated_entity_data = ilx_cli.update_entity(**update_entity_data.copy())

    assert updated_entity_data['label'] == label
    assert updated_entity_data['definition'] == definition
    assert updated_entity_data['type'] == type
    assert updated_entity_data['comment'] == comment
    assert updated_entity_data['superclass'].rsplit('/', 1)[-1] == superclass
    # test if random synonym was added
    assert synonym in update_entity_data['synonyms']
    # test if dupclicates weren't created
    assert update_entity_data['synonyms'].count('test') == 1


def test_annotation():
    annotation_value = 'test_' + id_generator()
    resp = ilx_cli.add_annotation(**{
        'term_ilx_id': 'tmp_0101431', # brain ILX ID
        'annotation_type_ilx_id': 'tmp_0112771', # spont firing ILX ID
        'annotation_value': annotation_value,
    })
    assert resp['value'] == annotation_value
    resp = ilx_cli.delete_annotation(**{
        'term_ilx_id': 'tmp_0101431', # brain ILX ID
        'annotation_type_ilx_id': 'tmp_0112771', # spont firing ILX ID
        'annotation_value': annotation_value,
    })
    # If there is a response than it means it worked. If you try this again it will 404 if my net
    # doesnt catch it
    assert resp['id'] != None
    assert resp['value'] == ' '


def test_relationship():
    random_label = 'my_test100' + id_generator()
    entity_resp = ilx_cli.add_entity(**{
        'label': random_label,
        'type': 'term',
    })

    entity1_ilx = entity_resp['ilx']
    relationship_ilx = 'tmp_0112785' # is part of ILX ID
    entity2_ilx = 'tmp_0100001' #1,2-Dibromo chemical ILX ID

    relationship_resp = ilx_cli.add_relationship(**{
        'entity1_ilx': entity1_ilx,
        'relationship_ilx': relationship_ilx,
        'entity2_ilx': entity2_ilx,
    })

    assert relationship_resp['term1_id'] == ilx_cli.get_entity(entity1_ilx)['id']
    assert relationship_resp['relationship_tid'] == ilx_cli.get_entity(relationship_ilx)['id']
    assert relationship_resp['term2_id'] == ilx_cli.get_entity(entity2_ilx)['id']

    relationship_resp = ilx_cli.delete_relationship(**{
        'entity1_ilx': entity_resp['ilx'], # (R)N6 chemical ILX ID
        'relationship_ilx': relationship_ilx,
        'entity2_ilx': entity2_ilx,
    })

    # If there is a response than it means it worked.
    assert relationship_resp['term1_id'] == ' '
    assert relationship_resp['relationship_tid'] == ' '
    assert relationship_resp['term2_id'] == ' '


def test_entity_remote():
    random_label = 'test_' + id_generator(size=12)

    # TODO: commented out key/vals can be used for services test later
    entity = {
        'label': random_label,
        'type': 'term', # broken at the moment NEEDS PDE HARDCODED
        'definition': 'Part of the central nervous system',
        'comment': 'Cannot live without it',
        # 'subThingOf': 'http://uri.interlex.org/base/ilx_0108124', # ILX ID for Organ
        'subThingOf': 'http://uri.interlex.org/base/tmp_0108124', # ILX ID for Organ
        'synonyms': ['Encephalon', 'Cerebro'],
        'predicates': {
            'http://uri.interlex.org/base/tmp_0112771': 'sample_value', # spont firing beta ID | annotation
            'http://uri.interlex.org/base/tmp_0112785': 'http://uri.interlex.org/base/tmp_0100001', # relationship
        }
    }
    ilxremote_resp = ilxremote.add_entity(**entity)
    added_entity_data = ilx_cli.get_entity(ilxremote_resp['curie'])
    added_annotation = ilx_cli.get_annotation_via_tid(added_entity_data['id'])[0]
    added_relationship = ilx_cli.get_relationship_via_tid(added_entity_data['id'])[0]

    assert ilxremote_resp['label'] == entity['label']
    # assert ilxremote_resp['type'] == entity['type']
    assert ilxremote_resp['definition'] == entity['definition']
    # assert ilxremote_resp['comment'] == entity['comment']
    # assert ilxremote_resp['superclass'] == entity['superclass']
    assert ilxremote_resp['synonyms'][0] == entity['synonyms'][0]
    assert ilxremote_resp['synonyms'][1] == entity['synonyms'][1]

    assert added_annotation['value'] == 'sample_value'
    assert added_annotation['annotation_term_ilx'] == 'tmp_0112771'
    assert added_relationship['relationship_term_ilx'] == 'tmp_0112785'
    assert added_relationship['term2_ilx'] == 'tmp_0100001'

    entity = {
        'ilx_id': ilxremote_resp['curie'],
        'label': random_label + '_update',
        # 'type': 'term', # broken at the moment NEEDS PDE HARDCODED
        'definition': 'Updated definition!',
        'comment': 'Cannot live without it UPDATE',
        'subThingOf': 'http://uri.interlex.org/base/tmp_0108124', # ILX ID for Organ
        'synonyms': ['Encephalon', 'Cerebro_update'],
        'predicates_to_add': {
            # DUPCLICATE CHECK
            'http://uri.interlex.org/base/tmp_0112771': 'sample_value', # spont firing beta ID | annotation
            # NEW VALUES
            'http://uri.interlex.org/base/tmp_0112771': 'sample_value2', # spont firing beta ID | annotation
            'http://uri.interlex.org/base/tmp_0112785': 'http://uri.interlex.org/base/tmp_0100000', # relationship
        },
        'predicates_to_delete': {
            # DELETE ORIGINAL
            'http://uri.interlex.org/base/tmp_0112771': 'sample_value', # spont firing beta ID | annotation
            'http://uri.interlex.org/base/tmp_0112785': 'http://uri.interlex.org/base/tmp_0100001', # relationship
        }
    }
    ilxremote_resp = ilxremote.update_entity(**entity)
    added_entity_data = ilx_cli.get_entity(ilxremote_resp['curie'])
    added_annotations = ilx_cli.get_annotation_via_tid(added_entity_data['id'])
    added_relationships = ilx_cli.get_relationship_via_tid(added_entity_data['id'])

    assert ilxremote_resp['label'] == entity['label']
    # assert ilxremote_resp['type'] == entity['type']
    assert ilxremote_resp['definition'] == entity['definition']
    # assert ilxremote_resp['comment'] == entity['comment']
    # assert ilxremote_resp['superclass'] == entity['superclass']
    assert ilxremote_resp['synonyms'][0] == entity['synonyms'][0]
    assert ilxremote_resp['synonyms'][1] == entity['synonyms'][1]

    assert len(added_annotations) == 1
    assert len(added_relationships) == 1
    assert added_annotations[0]['annotation_term_ilx'] == 'tmp_0112771'
    assert added_annotations[0]['value'] == 'sample_value2'
    # would check term1_ilx, but whoever made it forgot to make it a key...
    assert added_relationships[0]['relationship_term_ilx'] == 'tmp_0112785'
    assert added_relationships[0]['term2_ilx'] == 'tmp_0100000'
