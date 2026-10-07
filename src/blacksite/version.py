"""Version constants shared by the server, the door client, and storage.

The protocol major is independent of the package version and is asserted
by both ends of the socket (02-architecture.md section 5.1, section 14).
The content and world schemas version the data files and the SQLite
database (02-architecture.md section 6.2, 01-entities.md conventions).
"""

from typing import Final

# Semantic package version; must match `version` in pyproject.toml.
PACKAGE_VERSION: Final[str] = "0.0.1"

# 02-architecture.md section 5.1: the server rejects a `hello` whose
# major it does not speak. Removal or meaning change of a field bumps it.
PROTOCOL_MAJOR: Final[int] = 1

# 02-architecture.md section 6.2 and 01-entities.md: every content file
# carries `schema`; the loader refuses a schema it does not know.
CONTENT_SCHEMA: Final[int] = 1

# 02-architecture.md section 6.2: migrations bring world.db up to this
# schema at start; the server refuses to open a newer one.
WORLD_SCHEMA: Final[int] = 1
