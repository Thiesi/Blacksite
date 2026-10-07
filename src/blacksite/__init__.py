"""Blacksite: a real-time multiplayer door game for NetBBS.

Subpackages: `server` (the game service), `door` (the caller client),
`admin` (the operator CLI), `bot` (the load-test client), and `content`
(the shipped data tree). See docs/design/02-architecture.md section 2.
"""

from blacksite.version import PACKAGE_VERSION

__version__: str = PACKAGE_VERSION

__all__ = ["__version__"]
