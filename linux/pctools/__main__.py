"""Einstiegspunkt: python3 -m pctools"""
import sys

from .server import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
