"""Permite `python -m anonimizador documento.txt --modo pseudonimo`."""

import sys

from anonimizador.cli import main

if __name__ == "__main__":
    sys.exit(main())
