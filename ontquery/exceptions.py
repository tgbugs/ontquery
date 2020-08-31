class OntQueryError(Exception):
    pass


class NotFoundError(OntQueryError):
    pass


class ManyResultsError(OntQueryError):
    pass


class NoExplicitIdError(OntQueryError):
    pass


class ReadOnlyError(OntQueryError):
    pass


class ShouldNotHappenError(OntQueryError):
    pass


class FetchingError(OntQueryError):
    """ A really good looking error you've got there! """


class NoApiKeyError(OntQueryError):
    """ No api key has been set """
