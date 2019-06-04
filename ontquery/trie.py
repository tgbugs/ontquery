from unicodedata import category

NAME_START_CATEGORIES = ["Ll", "Lu", "Lo", "Lt", "Nl"]
SPLIT_START_CATEGORIES = NAME_START_CATEGORIES + ['Nd']
NAME_CATEGORIES = NAME_START_CATEGORIES + ["Mc", "Me", "Mn", "Lm", "Nd"]
ALLOWED_NAME_CHARS = ["\u00B7", "\u0387", "-", ".", "_", ":"]
XMLNS = "http://www.w3.org/XML/1998/namespace"


def split_uri(uri, split_start=SPLIT_START_CATEGORIES):
    if uri.startswith(XMLNS):
        return (XMLNS, uri.split(XMLNS)[1])
    length = len(uri)
    for i in range(0, length):
        c = uri[-i - 1]
        if not category(c) in NAME_CATEGORIES:
            if c in ALLOWED_NAME_CHARS:
                continue
            for j in range(-1 - i, length):
                if category(uri[j]) in split_start or uri[j] == "_":
                    # _ prevents early split, roundtrip not generate
                    ns = uri[:j]
                    if not ns:
                        break
                    ln = uri[j:]
                    return (ns, ln)
            break
    raise ValueError("Can't split '{}'".format(uri))


def insert_trie(trie, value):  # aka get_subtrie_or_insert
    """ Insert a value into the trie if it is not already contained in the trie.
        Return the subtree for the value regardless of whether it is a new value
        or not. """
    if value in trie:
        return trie[value]
    multi_check = False
    for key in tuple(trie.keys()):
        if len(value) > len(key) and value.startswith(key):
            return insert_trie(trie[key], value)
        elif key.startswith(value):  # we know the value is not in the trie
            if not multi_check:
                trie[value] = {}
                multi_check = True  # there can be multiple longer existing prefixes
            dict_ = trie.pop(key)  # does not break strie since key<->dict_ remains unchanged
            trie[value][key] = dict_
    if value not in trie:
        trie[value] = {}
    return trie[value]


def insert_strie(strie, trie, value):
    if value not in strie:
        strie[value] = insert_trie(trie, value)


def get_longest_namespace(trie, value):
    for key in trie:
        if value.startswith(key):
            out = get_longest_namespace(trie[key], value)
            if out is None:
                return key
            else:
                return out


def get_namespaces(trie, value):
    for key in trie:
        if value.startswith(key):
            yield key
            for ns in get_namespaces(trie[key], value):
                if ns is not None:
                    yield ns
