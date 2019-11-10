try:
    import orthauth as oa
    auth = oa.configure_relative('auth-config.py')
    class deco:
        scigraph_api_key = auth.tangential_init('api_key', 'scigraph-api-key')
        interlex_api_key = auth.tangential_init('api_key', 'interlex-api-key')
        interlex_basic_u = auth.tangential_init('_basic_auth_user', 'interlex-basic-auth-user')
        interlex_basic_p = auth.tangential_init('_basic_auth_pass', 'interlex-basic-auth-pass')
except ModuleNotFoundError:
    class deco:
        scigraph_api_key = lambda cls: cls
        interlex_api_key = lambda cls: cls
        interlex_basic_u = lambda cls: cls
        interlex_basic_p = lambda cls: cls
