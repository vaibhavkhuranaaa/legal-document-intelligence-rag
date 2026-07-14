"""Command-line entry point for the ingestion pipeline.

Wires together `run_pipeline`'s dependencies (settings, storage, Azure
client, logger) and invokes it. This is the one place in the codebase
allowed to construct infrastructure objects — `pipeline.py` and everything
it depends on receives them by injection, never constructs them itself (see
the Phase 1 orchestration design review).

No CLI flags override configuration: `IngestionSettings` (env-driven) is the
single source of truth for input/output directories and Azure credentials,
per ADR-0008. Adding flag-based overrides here would create a second,
competing configuration path.

Exit code is 0 whenever the run completes and produces a report, even if
individual documents failed — per-document failures are expected batch
outcomes, surfaced through the manifest report, not the process exit code.
Exit code is 1 only when the run could not complete at all (bad credentials,
an I/O failure writing the run report, or any other unhandled error).
"""

import sys

from legal_rag.ingestion.client import AzureDocumentIntelligenceClient
from legal_rag.ingestion.config import get_settings
from legal_rag.ingestion.logging_config import configure_logging, get_logger
from legal_rag.ingestion.models import ExtractionStatus, RunReport
from legal_rag.ingestion.pipeline import run_pipeline
from legal_rag.ingestion.storage.factory import build_storage_backend


def _summarize(report: RunReport) -> str:
    succeeded = sum(
        1 for entry in report.entries if entry.extraction_status == ExtractionStatus.SUCCESS
    )
    failed = len(report.entries) - succeeded
    return (
        f"Run {report.run_id} complete: {len(report.entries)} document(s) processed, "
        f"{succeeded} succeeded, {failed} failed."
    )


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)

    try:
        settings = get_settings()
        storage = build_storage_backend(settings)
        client = AzureDocumentIntelligenceClient(settings)
        report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)
    except Exception:
        logger.exception("ingestion run failed to complete")
        print("Ingestion run failed to complete; see logs for details.", file=sys.stderr)
        return 1

    print(_summarize(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
