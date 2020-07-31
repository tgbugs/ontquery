# ontquery
[![PyPI version](https://badge.fury.io/py/ontquery.svg)](https://pypi.org/project/ontquery/)
[![Build Status](https://travis-ci.org/tgbugs/ontquery.svg?branch=master)](https://travis-ci.org/tgbugs/ontquery)
[![Coverage Status](https://coveralls.io/repos/github/tgbugs/ontquery/badge.svg?branch=master)](https://coveralls.io/github/tgbugs/ontquery?branch=master)

a framework querying ontology terms

# Installation
Ontquery supports two different use cases each with their own installation instructions.  

By default ontquery installs only the stripped down core libraries so that it can be embedded an reused in
other applications that need to reduce their dependnecies. For this use case packages can include ontquery
as a dependency in their package requirements without any special changes e.g. `ontquery>=0.0.6`.  

The second use case enables remote services via a plugin infrastructure.
To install this version you should install or require using the [pip extras syntax](https://packaging.python.org/tutorials/installing-packages/#installing-setuptools-extras) e.g. `pip install ontquery[services]>=0.6.0`.

# SciCrunch api key
If you don't have your own SciGraph instance you will need a SciCunch API key in order to run the demos (e.g. `python __init__.py`).

To do this go to SciCrunch and [register for an account](https://scicrunch.org/register) and then [get an api key](https://scicrunch.org/account/developer).

You can then set the `SCICRUNCH_API_KEY` environment variable.
For example in bash `export SCICRUNCH_API_KEY=my-api-key`.

See https://github.com/tgbugs/ontquery/blob/db8cad7463704bce9010651c3744452aa5370114/ontquery/__init__.py#L557-L558 for how to pass the key in.

# SciGraphRemote Usage
```python
from ontquery import OntQuery, SciGraphRemote, OntTerm, OntCuries
from ontquery.plugins.namespaces import CURIE_MAP

curies = OntCuries(CURIE_MAP)
query = OntQuery(SciGraphRemote())
OntTerm.query = query
```
```python
query('mouse')
```
3 potential matches are shown:
```python
Query {'term': 'mouse', 'limit': 10} returned more than one result. Please review.

OntTerm('NCBITaxon:10090', label='Mus musculus', synonyms=['mouse', 'house mouse', 'mice C57BL/6xCBA/CaJ hybrid', 'Mus muscaris'])

OntTerm('NCBITaxon:10088', label='Mus <mouse, genus>', synonyms=['mouse', 'Mus', 'mice'])

OntTerm('BIRNLEX:167', label='Mouse', synonyms=['mouse', 'Mus musculus', 'house mouse'])
```

The one we are looking for is `Mus musculus`, and we can select that with
`OntTerm('NCBITaxon:10090', label='Mus musculus')` or with `OntTerm(curie='NCBITaxon:10090')`.

This workflow works for a variety of categories:
* species (e.g. 'mouse', 'rat', 'rhesus macaque')
* brain area (e.g. 'hippocampus', 'CA1', 'S1')
* cell type (e.g. 'mossy cell', 'pyramidal cell')
* institution (e.g. 'UC San Francisco', 'Brown University')
* disease (e.g. "Parkinson's Disease", 'ALS')

# Building for release
`python setup.py sdist --release && python setup.py bdist_wheel --universal --release`
Building a release requires a working install of pyontutils in order to build the
scigraph client library. The `--release` tells setup to build the scigraph client.

# Related issues

https://github.com/NeurodataWithoutBorders/nwb-schema/issues/1#issuecomment-368741867

https://github.com/NeurodataWithoutBorders/nwb-schema/issues/1#issuecomment-369215854

# InterlexRemote Notes
ilx_id and any key that takes a uri value can also be given a curie of that uri or a fragment and it will still work.

# InterLexRemote Usage
To access InterLex programatically you can set `SCICRUNCH_API_KEY` or
you can set `INTERLEX_API_KEY` either will work, but `INTERLEX_API_KEY`
has priority if both are set.

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
```
