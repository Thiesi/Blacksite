"""Entry point for `python -m blacksite.door`, the NetBBS native stdio door.

NetBBS launches this with an argv list, never a shell, so it must work
without the console script (02-architecture.md section 8.1).
"""

import sys


def main() -> int:
    """Report that this entry point is not implemented yet."""
    print("blacksite door: not implemented (see docs/plan/slices/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
