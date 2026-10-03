from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
).read_text(encoding="utf-8")


def test_release_emits_generic_intent_without_rendering_gitops() -> None:
    assert "actions/workflows/workload-release.yml/dispatches" in WORKFLOW
    assert "contract_version" in WORKFLOW
    assert "--arg component inference" in WORKFLOW
    assert "runtime_config" in WORKFLOW
    assert "config_schema_digest" in WORKFLOW
    assert "permission-actions: write" in WORKFLOW
    assert "cosign sign" in WORKFLOW

    forbidden = (
        "environments/production",
        "gh pr create",
        "git checkout -b",
        "sed -i",
        "permission-contents: write",
        "permission-pull-requests: write",
    )
    assert all(value not in WORKFLOW for value in forbidden)
