"""OrphanDiskAnalyzer – diskState == Unattached → orphan_disk finding."""
from __future__ import annotations
from api.analysis.base import Finding, ArmPropertyAnalyzer


class OrphanDiskAnalyzer(ArmPropertyAnalyzer):
    RESOURCE_TYPE = "microsoft.compute/disks"

    def _check(self, resource: dict, cost_map: dict[str, float]) -> Finding | None:
        props = self._arm(resource["resource_id"], api_version="2023-10-02")
        if not props:
            return None
        disk_state = props.get("properties", {}).get("diskState", "")
        if disk_state.lower() == "unattached":
            return self._finding(
                resource, cost_map,
                finding_type="orphan_disk",
                severity="medium",
                reason="Managed disk is unattached (diskState=Unattached).",
            )
        return None