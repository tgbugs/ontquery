class OntQueryError(Exception):
    pass


class NotFoundError(OntQueryError):
    pass


class ManyResultsError(OntQueryError):
    pass


class NoExplicitIdError(OntQueryError):
    pass


class ShouldNotHappenError(OntQueryError):
    pass
