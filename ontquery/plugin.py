from pkg_resources import iter_entry_points
from ontquery.services import OntService

entry_points = {'ontquery.plugins.services': OntService}

_plugins = {}

# register plugins from outside
for entry_point in entry_points:
    for ep in iter_entry_points(entry_point):
        _plugins[ep.name] = PKGPlugin(ep.name, ep)

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


register('rdflib', 'ontquery.plugins.services', 'rdflibLocal')
register('InterLex', 'ontquery.plugins.services', 'InterLexRemote')
register('SciGraph', 'ontquery.plugins.services', 'SciGraphRemote')
register('SciCrunch', 'ontquery.plugins.services', 'SciCrunchRemote')
register('GitHub', 'ontquery.plugins.services', 'GitHubRemote')
register('iris', 'ontquery.plugins.services', 'StaticIriRemote')

