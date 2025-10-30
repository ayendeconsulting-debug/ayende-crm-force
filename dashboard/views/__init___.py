"""
Dashboard views package
"""
from .main import *
from . import integration
from . import sync_views  # ← ADD THIS LINE

# Re-export everything from main
import sys
from . import main
for name in dir(main):
    if not name.startswith('_'):
        setattr(sys.modules[__name__], name, getattr(main, name))