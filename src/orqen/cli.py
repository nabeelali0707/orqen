"""Command-line entry point for reproducible local experiments."""

import argparse
from importlib.metadata import version


def main() -> None:
    parser = argparse.ArgumentParser(prog="orqen", description="Adaptive Agent Orchestrator")
    parser.add_argument("--version", action="version", version=f"orqen {version('orqen')}")
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
