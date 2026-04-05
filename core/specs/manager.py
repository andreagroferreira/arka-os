"""Spec manager — lifecycle management for Living Specs."""

from pathlib import Path
from typing import Optional

import yaml

from core.specs.schema import (
    Spec, SpecStatus, SpecSection, SpecDelta,
    AcceptanceCriterion, SpecMetadata, SectionStatus,
)


class SpecManager:
    """Manages the lifecycle of Living Specs.

    Handles creation, loading, saving, status transitions,
    and the reusable spec library.
    """

    def __init__(self, specs_dir: str | Path = "") -> None:
        self._specs: dict[str, Spec] = {}
        self._specs_dir = Path(specs_dir) if specs_dir else None

    def create(
        self,
        spec_id: str,
        title: str,
        description: str = "",
        project: str = "",
        department: str = "",
        sections: list[dict] | None = None,
    ) -> Spec:
        """Create a new spec."""
        from datetime import datetime

        spec_sections = []
        for s in (sections or []):
            criteria = [
                AcceptanceCriterion(id=f"ac-{i+1}", description=c)
                for i, c in enumerate(s.get("acceptance_criteria", []))
            ]
            spec_sections.append(SpecSection(
                id=s.get("id", f"section-{len(spec_sections)+1}"),
                title=s.get("title", ""),
                content=s.get("content", ""),
                acceptance_criteria=criteria,
            ))

        spec = Spec(
            id=spec_id,
            title=title,
            description=description,
            status=SpecStatus.DRAFT,
            metadata=SpecMetadata(
                project=project,
                department=department,
                created_at=datetime.now().isoformat(),
            ),
            sections=spec_sections,
        )

        self._specs[spec_id] = spec
        return spec

    def get(self, spec_id: str) -> Optional[Spec]:
        """Get a spec by ID."""
        return self._specs.get(spec_id)

    def approve(self, spec_id: str, approved_by: str = "") -> bool:
        """Approve a spec for implementation."""
        spec = self._specs.get(spec_id)
        if spec is None or spec.status not in (SpecStatus.DRAFT, SpecStatus.REVIEW):
            return False
        spec.status = SpecStatus.APPROVED
        spec.metadata.approved_by = approved_by
        from datetime import datetime
        spec.metadata.approved_at = datetime.now().isoformat()
        return True

    def start_implementation(self, spec_id: str) -> bool:
        """Mark spec as in-progress."""
        spec = self._specs.get(spec_id)
        if spec is None or spec.status != SpecStatus.APPROVED:
            return False
        spec.status = SpecStatus.IN_PROGRESS
        return True

    def complete(self, spec_id: str) -> bool:
        """Mark spec as completed."""
        spec = self._specs.get(spec_id)
        if spec is None or spec.status != SpecStatus.IN_PROGRESS:
            return False
        spec.status = SpecStatus.COMPLETED
        return True

    def list_all(self, status: Optional[SpecStatus] = None) -> list[Spec]:
        """List all specs, optionally filtered by status."""
        if status:
            return [s for s in self._specs.values() if s.status == status]
        return list(self._specs.values())

    def save_to_yaml(self, spec_id: str, path: str | Path) -> bool:
        """Save a spec to a YAML file."""
        spec = self._specs.get(spec_id)
        if spec is None:
            return False
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = spec.model_dump(mode="json")
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True

    def load_from_yaml(self, path: str | Path) -> Spec:
        """Load a spec from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        spec = Spec.model_validate(data)
        self._specs[spec.id] = spec
        return spec

    def extract_patterns(self, spec_id: str) -> list[str]:
        """Extract reusable patterns from a completed spec.

        Patterns are sections or approaches that worked well and
        can be reused in future specs.
        """
        spec = self._specs.get(spec_id)
        if spec is None or spec.status != SpecStatus.COMPLETED:
            return []

        patterns = []
        for section in spec.sections:
            if section.status == SectionStatus.IMPLEMENTED and not section.implementation_notes:
                patterns.append(f"[{spec.metadata.department}] {section.title}: {section.content[:100]}")
            elif section.status == SectionStatus.MODIFIED:
                delta = next((d for d in spec.deltas if d.section_id == section.id), None)
                if delta:
                    patterns.append(
                        f"[{spec.metadata.department}] {section.title}: "
                        f"Originally '{delta.original[:50]}', changed to '{delta.actual[:50]}' "
                        f"because: {delta.reason[:50]}"
                    )

        spec.patterns = patterns
        return patterns

    @property
    def total_specs(self) -> int:
        return len(self._specs)

    def summary(self) -> dict:
        """Summary of all specs."""
        by_status = {}
        for spec in self._specs.values():
            by_status[spec.status.value] = by_status.get(spec.status.value, 0) + 1
        return {
            "total": self.total_specs,
            "by_status": by_status,
        }
