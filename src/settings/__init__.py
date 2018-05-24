import os

from .base import *

try:
    running_env = os.environ.get('ENV', 'dev')
    if running_env:
        import importlib
        module_name = "settings.%s" % running_env.lower()
        module = importlib.import_module(module_name)
        for name in vars(module):
            v = getattr(module, name)
            globals()[name] = v
        print('Loaded settings for %s environment' % running_env)
except ImportError as error:
    print('No extra setting file detected')
