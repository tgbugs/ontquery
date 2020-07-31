# Project Details

InterLexClient is meant to help outside curators add entities and annotations in an efficient process.

## Prerequisites

- python==3.65 +
- requests==2.18.4 +
- pytest==3.10.0 +

```bash
pip3 install requests
pip3 install pytest
```

## API_KEY

Get your api_key via [SciCrunch](https://scicrunch.org/)
1. Register
2. Login
3. While on home page go to MY ACCOUNT. API KEYS will be 4th from the bottom
4. Provide Password
5. Click [Generate an API key] in the middle of the screen
6. copy and paste the 32 character api_key to .bashrc or .zshrc (if using zsh)

----
##### How it should look in your .bashrc or .zshrc file:
```bash
export INTERLEX_API_KEY="YOUR API KEY HERE"
```
----

## Running the tests

Pytest with -v option for verbose

```bash
pytest -v test/test_interlex_client.py
```

## Directions in how to use InterLexClient

##### Importing:

```python
from ontquery.interlex import interlex_client
```

##### Setup for **TEST**:
*This Should be used to test if your code works first*

```python
ilx_cli = interlex_client('test3.scicrunch.org')
```

##### Setup for **PRODUCTION**:

```python
ilx_cli = interlex_client('scicrunch.org')
```

##### Adding Entity Needed:

```python
added_entity_data = ilx_cli.add_entity(
    label = '',
    type = '', # term, fde, cde, pde, relationship, annotation
)
```

#### Adding Entity Example

```python
added_entity_data = ilx_cli.add_entity(
    label = 'Label of entity you wish to create',
    type = 'A type that should be one of the following: term, relationship, annotation, cde, fde, pde',
    # subThingOf can take either iri or curie form of ID
    subThingOf = 'http://uri.interlex.org/base/ilx_0108124', # superclass or subClassOf ILX ID
    definition = 'Entities definition',
    comment = 'A comment to help understand entity',
    synonyms = ['synonym1', {'literal': 'synonym2', 'type': 'hasExactSynonym'}, 'etc'],
    # exisiting IDs are List[dict] with keys iri & curie
    existing_ids = [{'iri':'https://example.org/example_1', 'curie':'EXAMPLE:1'}],
    cid = 504,  # community ID
    predicates = {
        # annotation_entity_ilx_id : 'annotation_value',
        'http://uri.interlex.org/base/tmp_0381624': 'PMID:12345', # annotation
        # relationship_entity_ilx_id : 'entity2_ilx_id',
        'http://uri.interlex.org/base/ilx_0112772': 'http://uri.interlex.org/base/ilx_0100001', # relationship
    }
)
```

#### Updating Entity Example

```python
updated_entity = update_entity( 
    ilx_id='ilx_1234567', 
    label='Brain', 
    type='term',  # options: term, pde, fde, cde, annotation, or relationship 
    definition='Official definition for entity.', 
    comment='Additional casual notes for the next person.', 
    superclass='ilx_1234567', 
    add_synonyms=[{ 
        'literal': 'Better Brains',  # label of synonym 
        'type': 'obo:hasExactSynonym',  # Often predicate defined in ref ontology. 
    }], 
    delete_synonyms=[{ 
        'literal': 'Brains',  # label of synonym 
        'type': 'obo:hasExactSynonym',  # Often predicate defined in ref ontology. 
    }], 
    add_existing_ids=[{ 
        'iri': 'http://purl.obolibrary.org/obo/UBERON_0000956', 
        'curie': 'UBERON:0000956',  # Obeys prefix:id structure. 
        'preferred': '1',  # Can be 0 or 1 with a type of either str or int. 
    }], 
    delet_existing_ids=[{ 
        'iri': 'http://purl.obolibrary.org/obo/UBERON_0000955', 
        'curie': 'UBERON:0000955',  # Obeys prefix:id structure. 
    }], 
    cid='504',  # SPARC Community, 
    status='0',  # remove delete 
)
``` 

Both functions add_entity() and add_annotation() will return a dictionary of the populated data
for the entity or term even if it already existed. If it already exists it will just print a
warning saying it already exists, but again, it will return the dictionary of its populated
data anyway.

Because of this simple logic, it would be perfectly fine to be lazy and re-add any entities
or annotations if it crashed half way through because of a string error on your end once it is
fixed.

##### Example add_entity output

```json
{
    "id": "304713",
    "orig_uid": "34142",
    "uid": "34142",
    "orig_cid": "0",
    "cid": "0",
    "ilx": "tmp_0381629",
    "label": "brain",
    "type": "pde",
    "definition": "Part of the central nervous system",
    "comment": "Cannot live without it",
    "version": "1",
    "status": "0",
    "display_superclass": "1",
    "orig_time": "1541459612",
    "time": "1541459612",
    "synonyms": [{
        "id": "375931",
        "tid": "304713",
        "literal": "Encephalon",
        "type": "",
        "time": "1541459612",
        "version": "1",
    }],
    "superclasses": [{
        "id": 340809,
        "tid": 304820,
        "superclass_tid": 8125,
        "version": 1,
        "time": 1541618830,
    }],
    "existing_ids": [
        {
            "id": "416448",
            "tid": "304713",
            "curie": "BIRNLEX:796",
            "iri": "http://uri.neuinfo.org/nif/nifstd/birnlex_796",
            "curie_catalog_id": "0",
            "version": "1",
            "time": "1541459612",
            "preferred": "1"
        },
        {
            "id": "416449",
            "tid": "304713",
            "curie": "ILX:0381629",
            "iri": "http://uri.interlex.org/base/ilx_0381629",
            "curie_catalog_id": "3",
            "version": "1",
            "time": "1541459613",
            "preferred": "0"
        }
    ],
    "relationships": [],
    "mappings": [],
    "annotations": [],
    "ontologies": []
}
```

## Notes
Dictionay outputs from `add_entity` and `update_entity` will not always have string type for the values.
That does not matter for the api endpoints, but just in case this data is used somewhere else, this should be noted.

## Author

Troy Sincomb

## License

[MIT](https://choosealicense.com/licenses/mit/)
