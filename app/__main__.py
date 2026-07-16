import sys

from .cli import main

if __name__ == "__main__":
    # No subcommand still means HTTP on 0.0.0.0:6002, as before.
    sys.exit(main())
