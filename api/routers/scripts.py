"""
Scripts router.

POST /api/v1/scripts/generate      → ScriptBuilder generates TWO timestamped PS1
                                     scripts per run: tagging + deletion, both
                                     uploaded to optimizer-exports blob container.
GET  /api/v1/scripts/download-all  → streams ZIP of all scripts for latest run

Class hierarchy
───────────────
ScriptBuilder
  – __init__(findings, run_id, exports_svc)  ← ExportsContainerService injected
  – build_tagging_script()   → str   (az resource tag … for each finding)
  – build_deletion_script()  → str   (az resource delete … READY TO RUN)
  – generate()               → tuple[ScriptRecord, ScriptRecord]
                                builds both scripts, uploads them with
                                timestamped filenames, returns two dicts
                                ready for DB insertion.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import get_db

logger = logging.getLogger(__name__)
from api.dependencies import get_exports_storage_dep
from api.models import JobRun, OrphanFinding, RemediationScript
from api.schemas import ScriptOut
from api.services.storage import ExportsContainerService

router = APIRouter(prefix="/api/v1/scripts", tags=["scripts"])

_TMP_DIR = Path("/tmp/scripts")


# ── TypedDict for script record data ──────────────────────────────────────────

class ScriptRecord(TypedDict):
    id: str
    run_id: str
    filename: str
    script_type: str
    resource_count: int
    generated_at: datetime
    blob_path: str


# ── ScriptBuilder ─────────────────────────────────────────────────────────────

class ScriptBuilder:
    """
    Builds two PowerShell remediation scripts for a set of findings.

    tagging  – immediately executable: tags resources as orphan-candidate
    deletion – immediately executable: deletes resources (NOT commented out)

    Both filenames include a UTC timestamp so each run produces unique,
    non-overwriting blobs in the storage account container:
        scripts/{run_id}/tagging_{run_id[:8]}_{timestamp}.ps1
        scripts/{run_id}/deletion_{run_id[:8]}_{timestamp}.ps1
    """

    _HEADER_BANNER = (
        "# ================================================================\n"
        "# Cloud Cost Optimizer - Remediation Script\n"
        "# {script_type_label}\n"
        "# Generated : {ts}\n"
        "# Run ID    : {run_id}\n"
        "# Findings  : {count}\n"
        "# ================================================================\n"
    )

    def __init__(
        self,
        findings: list[OrphanFinding],
        run_id: str,
        exports_svc: ExportsContainerService,
    ) -> None:
        self._findings = findings
        self._run_id = run_id
        self._exports = exports_svc
        self._ts = datetime.now(timezone.utc)
        self._ts_str = self._ts.strftime("%Y%m%dT%H%M%SZ")
        self._ts_display = self._ts.strftime("%Y-%m-%d %H:%M UTC")

    # ── script content builders ───────────────────────────────────────────────

    def build_tagging_script(self) -> str:
        """Generate tagging-only script (safe to run immediately)."""
        lines = [
            self._header("TAGGING SCRIPT – Tags resources as orphan-candidate"),
            "# This script is safe to run; it only adds metadata tags.",
            "# Review the tagged resources in the Azure portal before deletion.",
            "",
            "# ── Tag resources ──────────────────────────────────────────────",
            "",
        ]
        for f in self._findings:
            safe = f.resource_name.replace("'", "''")
            lines += [
                f"# [{f.finding_type.upper()}] {safe} | Est. ${f.estimated_monthly_cost_usd:.2f}/mo",
                f"# Reason: {f.reason}",
                (
                    f"az resource tag --ids '{f.resource_id}' "
                    "--tags orphan-candidate=true FinOps-Action=review "
                    f"FinOps-FindingType={f.finding_type} FinOps-RunId={self._run_id[:8]}"
                ),
                "",
            ]
        return "\n".join(lines)

    def build_deletion_script(self) -> str:
        """
        Generate deletion script — commands are LIVE (not commented out).
        WARNING: Run only after reviewing the tagging script output.
        """
        lines = [
            self._header("DELETION SCRIPT – Permanently removes identified resources"),
            "# WARNING: This script PERMANENTLY DELETES Azure resources.",
            "# Run ONLY after reviewing and confirming the tagging script output.",
            "# Consider running with --dry-run or in a non-production subscription first.",
            "",
            "# ── Confirm operator intent ────────────────────────────────────",
            '$confirm = Read-Host "Type YES to proceed with deletion"',
            'if ($confirm -ne "YES") { Write-Host "Aborted."; exit 1 }',
            "",
            "# ── Delete resources ───────────────────────────────────────────",
            "",
        ]
        for f in self._findings:
            safe = f.resource_name.replace("'", "''")
            lines += [
                f"# [{f.finding_type.upper()}] {safe} | Est. ${f.estimated_monthly_cost_usd:.2f}/mo",
                f"Write-Host 'Deleting: {safe}'",
                f"az resource delete --ids '{f.resource_id}' --yes",
                "",
            ]
        lines += [
            "",
            "Write-Host 'Deletion complete. Verify in the Azure portal.'",
        ]
        return "\n".join(lines)

    # ── generate + upload ─────────────────────────────────────────────────────

    def generate(self) -> tuple[ScriptRecord, ScriptRecord]:
        """Build, persist locally, upload both scripts. Return two ScriptRecord dicts."""
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(
            "[run=%s] Generating remediation scripts | findings=%d | ts=%s",
            self._run_id[:8], len(self._findings), self._ts_str,
        )
        tagging_rec  = self._make_record("tagging",  self.build_tagging_script())
        deletion_rec = self._make_record("deletion", self.build_deletion_script())
        logger.info(
            "[run=%s] Both scripts generated successfully | tagging=%s | deletion=%s",
            self._run_id[:8], tagging_rec["blob_path"], deletion_rec["blob_path"],
        )
        return tagging_rec, deletion_rec

    def _make_record(self, script_type: str, content: str) -> ScriptRecord:
        filename  = f"{script_type}_{self._run_id[:8]}_{self._ts_str}.ps1"
        blob_path = f"scripts/{self._run_id}/{filename}"
        local     = _TMP_DIR / filename
        logger.debug("[run=%s] Writing %s script locally | path=%s",
                     self._run_id[:8], script_type, local)
        local.write_text(content, encoding="utf-8")
        logger.info("[run=%s] Uploading %s script | blob=%s | size_chars=%d",
                    self._run_id[:8], script_type, blob_path, len(content))
        self._exports.upload_export(blob_path, local)
        logger.info("[run=%s] Script uploaded | type=%s | blob=%s",
                    self._run_id[:8], script_type, blob_path)
        return ScriptRecord(
            id=str(uuid.uuid4()),
            run_id=self._run_id,
            filename=filename,
            script_type=script_type,
            resource_count=len(self._findings),
            generated_at=self._ts,
            blob_path=blob_path,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _header(self, label: str) -> str:
        return self._HEADER_BANNER.format(
            script_type_label=label,
            ts=self._ts_display,
            run_id=self._run_id,
            count=len(self._findings),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=list[ScriptOut])
def generate_scripts(
    db: Session = Depends(get_db),
    exports: ExportsContainerService = Depends(get_exports_storage_dep),
):
    """Generate timestamped tagging + deletion scripts for the latest run."""
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No job runs found.")

    run_id = latest.id
    findings = db.query(OrphanFinding).filter(OrphanFinding.run_id == run_id).all()
    if not findings:
        logger.warning("[run=%s] No findings found — cannot generate scripts", run_id[:8])
        raise HTTPException(status_code=404, detail="No findings for latest run.")

    logger.info("[run=%s] Script generation requested | findings=%d", run_id[:8], len(findings))
    tagging_rec, deletion_rec = ScriptBuilder(findings, run_id, exports).generate()

    records = []
    for rec in (tagging_rec, deletion_rec):
        orm_obj = RemediationScript(**rec)
        db.add(orm_obj)
        records.append(orm_obj)

    for f in findings:
        f.script_generated = True

    db.commit()
    for r in records:
        db.refresh(r)
    logger.info("[run=%s] Script records persisted to DB | count=2", run_id[:8])
    return [ScriptOut.model_validate(r) for r in records]


@router.get("/download-all")
def download_all_scripts(
    db: Session = Depends(get_db),
    exports: ExportsContainerService = Depends(get_exports_storage_dep),
):
    """Download ZIP of all scripts for the latest run."""
    latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No job runs found.")

    scripts = (
        db.query(RemediationScript)
        .filter(RemediationScript.run_id == latest.id)
        .all()
    )
    if not scripts:
        raise HTTPException(status_code=404, detail="No scripts generated. Call /generate first.")

    logger.info("[run=%s] Building ZIP | scripts=%d", latest.id[:8], len(scripts))
    buf = io.BytesIO()
    included = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in scripts:
            if s.blob_path:
                try:
                    zf.writestr(s.filename, exports.get_export_blob_bytes(s.blob_path))
                    included += 1
                except Exception as exc:
                    logger.error(
                        "[run=%s] Failed to fetch blob for ZIP | blob=%s | error=%s",
                        latest.id[:8], s.blob_path, exc,
                    )
    buf.seek(0)
    logger.info("[run=%s] ZIP ready | included=%d/%d", latest.id[:8], included, len(scripts))
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=remediation_scripts.zip"},
    )