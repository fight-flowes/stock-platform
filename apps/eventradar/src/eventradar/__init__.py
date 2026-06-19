"""eventradar — forward-looking event radar for the A-share market.

This package is intentionally tiny at this stage. The skeleton mirrors
``stockkb`` so the platform stays internally consistent, but every module
under :mod:`eventradar.sources.adapters`, :mod:`eventradar.normalize`, and
:mod:`eventradar.storage` is currently a placeholder. They are filled in
adapter-by-adapter, starting with the company-calendar adapter (M1).

The HTTP contract served by :mod:`eventradar.api` is locked in by
``calenderapp``'s ``EventradarProxyService`` and must stay stable.
"""

from .config import get_settings  # re-exported for convenience

__all__ = ["get_settings"]
__version__ = "0.0.1"
