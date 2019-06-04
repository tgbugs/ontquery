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
from interlex_client import InterLexClient

```

##### Setup for **BETA**:
*This Should be used to test if your code works first*

```python
ilx_cli = InterLexClient(
    base_url = "https://beta.scicrunch.org",
)
```

##### Setup for **PRODUCTION**:

```python
ilx_cli = InterLexClient(
    base_url = "https://scicrunch.org",
)
```

##### Adding Entity Options:

```python
added_entity_data = ilx_cli.add_entity(
    label = '',
    type = '',
    definition = '',
    comment = '',
    superclass = '',
    synonyms = ['',],
)
```

##### Adding Entity Needed:

```python
added_entity_data = ilx_cli.add_entity(
    label = '',
    type = '',
)
```

#### Adding Entity Example

```python
added_entity_data = ilx_cli.add_entity(
    label = 'brain',
    type = 'term',
    definition = 'Part of the central nervous system',
    comment = 'Cannot live without it',
    superclass = 'http://uri.interlex.org/base/ilx_0108124',
    synonyms = ['Encephalon', 'Cerebro'],
)
```

##### Adding Annotation (All 3 keys Needed)

```python
added_annotation_data = ilx_cli.add_annotation(
    "term_ilx_id": "",
    "annotation_type_ilx_id": "",
    "annotation_value": "",
)
```

##### Adding Annotation Example

```python
added_annotation_data = ilx_cli.add_annotation(
    "term_ilx_id": "http://uri.interlex.org/base/ilx_0101431", # brain ILX ID
    "annotation_type_ilx_id": "http://uri.interlex.org/base/tmp_0381624", # hasDbXref ILX ID
    "annotation_value": "This is a string you should add for value",
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

##### Example add_annotation output

```json
{
    "id": 118785,
    "tid": 1432,
    "annotation_tid": 304710,
    "value": "PMID:12345",
    "comment": "",
    "upvote": 0,
    "downvote": 0,
    "curator_status": "0",
    "withdrawn": "0",
    "term_version": 187,
    "annotation_term_version": 1,
    "orig_uid": 0,
    "orig_time": 1541472726,
    "annotation_term_label": "PubMed Annotation Source",
    "annotation_term_ilx": "tmp_0381624",
    "annotation_term_type": "annotation",
    "annotation_term_definition": ""
}
```

## Notes
Dictionay outputs from `add_entity` and `add_annotation` will not always have string type for the values.
That does not matter for the api endpoints, but just in case this data is used somewhere else, this should be noted.

## Author

Troy Sincomb

## License

[MIT](https://choosealicense.com/licenses/mit/)
