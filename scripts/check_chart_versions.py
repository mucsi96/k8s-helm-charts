"""Verify native action output validation before chart metadata is changed."""
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run(chart, counter, tag, success=True):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/set_chart_version.py"), str(chart), counter, tag], capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stderr


with tempfile.TemporaryDirectory(prefix="chart-metadata-") as directory:
    chart = Path(directory) / "Chart.yaml"
    chart.write_text('# Keep comments and other metadata\napiVersion: v2\nname: client-app\nversion: 0.1.0\nappVersion: "7"\n')
    run(chart, "23", "client-app-23.0.0")
    assert yaml.safe_load(chart.read_text()) == {"apiVersion": "v2", "name": "client-app", "version": "23.0.0", "appVersion": "7"}
    assert chart.read_text().startswith("# Keep comments")
    expected = chart.read_text()
    for counter, tag in [("23", "client-app-23"), ("23", "other-23.0.0"), ("23", "client-app-24.0.0"),
                         ("023", "client-app-023.0.0"), ("latest", "client-app-latest.0.0"), ("", "")]:
        run(chart, counter, tag, success=False)
        assert chart.read_text() == expected
    chart.write_text("apiVersion: v2\nname: client-app\n")
    run(chart, "23", "client-app-23.0.0", success=False)
    assert chart.read_text() == "apiVersion: v2\nname: client-app\n"

workflow = yaml.safe_load((ROOT / ".github/workflows/release.yaml").read_text())
steps = workflow["jobs"]["release"]["steps"]
version_steps = [step for step in steps if step.get("uses", "").startswith("mucsi96/get-next-version@")]
assert len(version_steps) == 8 and all(step["with"]["suffix"] == ".0.0" for step in version_steps)
assert not any("prepare_chart_version_tags" in step.get("run", "") for step in steps)
uploader = next(step for step in steps if step.get("uses", "").startswith("helm/chart-releaser-action@"))
assert uploader["with"]["skip_existing"] is True
print("Native suffix inputs, metadata updates and fail-closed legacy-output checks passed")
