"""Run the CLI when executing the package as a module."""

from hermetic.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
