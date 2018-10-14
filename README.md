# ontquery
[![PyPI version](https://badge.fury.io/py/ontquery.svg)](https://pypi.org/project/ontquery/)
[![Build Status](https://travis-ci.org/tgbugs/ontquery.svg?branch=master)](https://travis-ci.org/tgbugs/ontquery)

a framework querying ontology terms

# SciCrunch api key
If you don't have your own SciGraph instance you will need a SciCunch API key in order to run the demos (e.g. `python __init__.py`).

To do this go to SciCrunch and [register for an account](https://scicrunch.org/register) and then [get an api key](https://scicrunch.org/account/developer).

You can then set the `SCICRUNCH_API_KEY` environment variable.
For example in bash `export SCICRUNCH_API_KEY=my-api-key`.

See https://github.com/tgbugs/ontquery/blob/db8cad7463704bce9010651c3744452aa5370114/ontquery/__init__.py#L557-L558 for how to pass the key in.

# Usage
```python
from ontquery import OntQuery, SciGraphRemote, OntTerm, OntCuries

import os
from pyontutils.core import PREFIXES as uPREFIXES
curies = OntCuries(uPREFIXES)
api_key = os.environ['SCICRUNCH_API_KEY']
query = OntQuery(SciGraphRemote(api_key=api_key))
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

The one we are looking for is `Mus musculus`, and we can select that with `OntTerm(label='Mus musculus')` or with `OntTerm(curie='NCBITaxon:10090')`.

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
