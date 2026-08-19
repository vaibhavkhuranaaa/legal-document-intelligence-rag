from pathlib import Path

WORKFLOW = (Path(__file__).parents[1] / ".github" / "workflows" / "deploy.yml").read_text()


def test_deployment_separates_archive_upload_from_runtime_verification() -> None:
    assert 'git archive --format=zip --output "legal-rag-$SOURCE_SHA.zip" "$SOURCE_SHA"' in WORKFLOW
    assert "--restart false" in WORKFLOW
    assert "--track-status false" in WORKFLOW
    assert '"PORTFOLIO_SOURCE_SHA=$SOURCE_SHA"' in WORKFLOW
    assert '"$LIVE_URL/healthz"' in WORKFLOW
