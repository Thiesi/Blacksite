"""`blacksite serve` and `blacksite admin ...` convenience entry point."""

import sys

from blacksite.admin.__main__ import main as admin


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "admin":
        args = args[1:]
    return admin(args)


if __name__ == "__main__":
    sys.exit(main())
