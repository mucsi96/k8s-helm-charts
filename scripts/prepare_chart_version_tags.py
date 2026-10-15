"""Expose N.0.0 chart releases to the shared integer-tag version action locally."""
import argparse
from pathlib import Path
import re
import subprocess

import yaml


def git(repository, *args):
    return subprocess.run(["git", "-C", str(repository), *args], check=True, text=True, capture_output=True).stdout.strip()


def prepare(repository):
    chart_names = {yaml.safe_load(path.read_text())["name"] for path in (repository / "charts").glob("*/Chart.yaml")}
    tags = git(repository, "tag", "--list").splitlines()
    existing = set(tags)
    planned = []
    for name in sorted(chart_names):
        for tag in tags:
            match = re.fullmatch(rf"{re.escape(name)}-([1-9][0-9]*)\.0\.0", tag)
            if not match:
                continue
            alias = f"{name}-{match.group(1)}"
            commit = git(repository, "rev-parse", f"refs/tags/{tag}^{{commit}}")
            if alias in existing:
                if git(repository, "rev-parse", f"refs/tags/{alias}^{{commit}}") != commit:
                    raise ValueError(f"Refusing to overwrite {alias}: it conflicts with published {tag}")
            else:
                planned.append((alias, commit))
    # Validate all aliases first. Never replace existing refs or push these aliases.
    for alias, commit in planned:
        git(repository, "tag", alias, commit)
    return [alias for alias, _ in planned]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        aliases = prepare(args.repository)
    except (ValueError, subprocess.CalledProcessError, yaml.YAMLError) as error:
        parser.exit(1, f"Chart version preparation failed: {error}\n")
    print(f"Prepared {len(aliases)} runner-local chart version aliases: {', '.join(aliases)}")
