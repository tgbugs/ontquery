# ontquery
a framework querying ontology terms

# SciCrunch api key
If you don't have your own SciGraph instance you will need a SciCunch API key in order to run the demos (e.g. `python __init__.py`).

To do this go to SciCrunch and [register for an account](https://scicrunch.org/register) and then [get an api key](https://scicrunch.org/account/developer).

You can then set the `SCICRUNCH_API_KEY` environment variable.
For example in bash `export SCICRUNCH_API_KEY=my-api-key`.

See https://github.com/tgbugs/ontquery/blob/db8cad7463704bce9010651c3744452aa5370114/ontquery/__init__.py#L557-L558 for how to pass the key in.

# Related issues

https://github.com/NeurodataWithoutBorders/nwb-schema/issues/1#issuecomment-368741867

https://github.com/NeurodataWithoutBorders/nwb-schema/issues/1#issuecomment-369215854
