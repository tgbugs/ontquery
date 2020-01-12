from ontquery.services import OntService

entry_points = {'ontquery.plugins.services': OntService}

_plugins = {}

# calling pkg_resources import iter_entry_points is EXTREMELY SLOW
# so we are no longer supporting it, register your plugins manually
# I have no idea why setuptools is so insanely slow for this


class Plugin:
    def __init__(self, name, module_path, class_name):
        self.name = name
        self.module_path = module_path
        self.class_name = class_name
        self._class = None

    def getClass(self):
        if self._class is None:
            module = __import__(self.module_path, globals(), locals(), [""])
            self._class = getattr(module, self.class_name)
        return self._class


class PKGPlugin(Plugin):
    def __init__(self, name, ep):
        self.name = name
        self.ep = ep
        self._class = None

    def getClass(self):
        if self._class is None:
            self._class = self.ep.load()
        return self._class


def get(name):
    return _plugins[name].getClass()


def register(name, module_path, class_name):
    p = Plugin(name, module_path, class_name)
    _plugins[name] = p


register('InterLex', 'ontquery.plugins.services.interlex', 'InterLexRemote')
register('SciGraph', 'ontquery.plugins.services.scigraph', 'SciGraphRemote')
register('SciCrunch', 'ontquery.plugins.services.scigraph', 'SciCrunchRemote')
register('rdflib', 'ontquery.plugins.services.rdflib', 'rdflibLocal')
register('iris', 'ontquery.plugins.services.rdflib', 'StaticIriRemote')
register('GitHub', 'ontquery.plugins.services.rdflib', 'GitHubRemote')
