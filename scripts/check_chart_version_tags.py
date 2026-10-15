"""Reproduce mixed legacy/Helm release tags in an isolated real Git history."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "GIT_AUTHOR_NAME": "Chart fixture", "GIT_AUTHOR_EMAIL": "fixture@example.test",
       "GIT_COMMITTER_NAME": "Chart fixture", "GIT_COMMITTER_EMAIL": "fixture@example.test"}


def git(repository, *args):
    return subprocess.run(["git", "-C", str(repository), *args], check=True, text=True, capture_output=True, env=ENV).stdout.strip()


def prepare(repository, success=True):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_chart_version_tags.py"), "--repository", str(repository)], text=True, capture_output=True)
    assert (result.returncode == 0) == success, result.stderr


with tempfile.TemporaryDirectory(prefix="chart-version-tags-") as directory:
    repository = Path(directory)
    git(repository, "init", "-q")
    for name in ["client-app", "go-app", "rust-app"]:
        chart = repository / "charts" / name
        chart.mkdir(parents=True)
        (chart / "Chart.yaml").write_text(yaml.safe_dump({"apiVersion": "v2", "name": name, "version": "0.1.0"}))
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Initial chart fixture")
    initial = git(repository, "rev-parse", "HEAD")
    git(repository, "tag", "client-app-14")
    (repository / "charts/client-app/values.yaml").write_text("appPort: 8000\n")
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "Published Helm chart fixture")
    published = git(repository, "rev-parse", "HEAD")
    git(repository, "tag", "-a", "client-app-22.0.0", "-m", "Published client chart")
    git(repository, "tag", "go-app-1.0.0")
    git(repository, "tag", "unrelated-99.0.0")
    git(repository, "tag", "client-app-0.1.0")
    git(repository, "tag", "client-app-30.0.0-beta")
    prepare(repository)
    assert git(repository, "rev-parse", "client-app-22^{commit}") == published
    assert git(repository, "rev-parse", "go-app-1^{commit}") == published
    assert git(repository, "rev-parse", "client-app-14^{commit}") == initial
    aliases = set(git(repository, "tag", "--list").splitlines())
    assert "unrelated-99" not in aliases and "rust-app-1" not in aliases and "client-app-30" not in aliases
    prepare(repository)
    assert set(git(repository, "tag", "--list").splitlines()) == aliases
    git(repository, "tag", "-d", "client-app-22")
    git(repository, "tag", "client-app-22", initial)
    git(repository, "tag", "rust-app-1.0.0")
    prepare(repository, success=False)
    assert git(repository, "rev-parse", "client-app-22^{commit}") == initial
    assert "rust-app-1" not in git(repository, "tag", "--list").splitlines()

workflow = yaml.safe_load((ROOT / ".github/workflows/release.yaml").read_text())
steps = workflow["jobs"]["release"]["steps"]
preparation = next(index for index, step in enumerate(steps) if "prepare_chart_version_tags.py" in step.get("run", ""))
version_steps = [index for index, step in enumerate(steps) if step.get("uses", "").startswith("mucsi96/get-next-version@")]
assert version_steps and preparation < min(version_steps)
uploader = next(step for step in steps if step.get("uses", "").startswith("helm/chart-releaser-action@"))
assert uploader["with"]["skip_existing"] is True
assert "git push" not in (ROOT / "scripts/prepare_chart_version_tags.py").read_text()
print("Chart tag compatibility, idempotence, conflict protection and release configuration checks passed")
