"""Runtime patch for madmom Python 3.10+ and numpy compatibility.

Madmom has two compatibility issues:
1. Imports MutableSequence from collections instead of collections.abc (Python 3.10+)
2. Uses deprecated np.float, np.int which were removed in numpy 1.24+

This module patches both issues before madmom is imported.
"""
import collections
import collections.abc
import numpy as np


def patch_madmom():
    """Patch collections and numpy for madmom compatibility.

    Fixes:
    1. collections.MutableSequence for Python 3.10+
    2. np.float, np.int for numpy 1.24+

    This is safe because:
    - Only modifies if attributes don't exist
    - Applied before madmom import, so no side effects
    - Uses proper numpy types as replacements

    Call this before importing madmom to ensure compatibility.
    """
    # Fix collections.MutableSequence for Python 3.10+
    if not hasattr(collections, 'MutableSequence'):
        collections.MutableSequence = collections.abc.MutableSequence

    # Fix numpy.float, numpy.int for numpy 1.24+
    if not hasattr(np, 'float'):
        np.float = np.float64
    if not hasattr(np, 'int'):
        np.int = np.int_
