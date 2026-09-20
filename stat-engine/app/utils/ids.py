"""
CUID-compatible ID generation.

Prisma uses cuid() (v1) for all primary keys.  This module uses CUID2
with a fixed length of 25 characters, which produces unique, collision-
resistant string IDs compatible with the existing schema.
"""

from cuid2 import Cuid

_generator = Cuid(length=25)


def generate_cuid() -> str:
    """Generate a 25-character CUID2 string suitable for primary keys."""
    return _generator.generate()
