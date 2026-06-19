"""eventradar data sources.

Only :mod:`eventradar.sources.akshare_client` is allowed to import the
``akshare`` package; every adapter under :mod:`eventradar.sources.adapters`
goes through it. Keep that boundary — it's the difference between an
upstream API change rippling into one file vs the entire codebase.
"""

from .akshare_client import AkshareCallError, fetch_dataframe

__all__ = ["AkshareCallError", "fetch_dataframe"]
