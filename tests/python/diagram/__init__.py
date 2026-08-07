"""Package marker so this tree may share test basenames with tests/python/.

Without it pytest's ``prepend`` import mode names both
``tests/python/test_vendor_integrity.py`` and
``tests/python/diagram/test_vendor_integrity.py`` the same module and
aborts collection with "import file mismatch".
"""
