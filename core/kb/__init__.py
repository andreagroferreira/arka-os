"""Knowledge-base integrations that reach outside the machine.

Everything here goes through ``core.egress.policy`` before a byte
leaves. The package is deliberately absent from the critical path:
``tests/python/test_notebooklm_chokepoint.py`` asserts by import graph
that ``core/governance``, ``core/workflow`` and ``core/release`` never
import it, so an upstream tool breaking can stall research but never a
gate or a release.
"""
