"""Living Specs — bidirectional spec/code sync.

Specs are never stale. They track implementation status, record deltas,
and build a reusable library of validated specifications.
"""

from core.specs.schema import Spec, SpecStatus, SpecSection, SpecDelta
from core.specs.manager import SpecManager

__all__ = ["Spec", "SpecStatus", "SpecSection", "SpecDelta", "SpecManager"]
