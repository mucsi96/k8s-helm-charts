"""Apply verified shared-action outputs to Helm chart metadata."""
import argparse
from pathlib import Path
import re

import yaml


def update(chart, counter, tag):
    if not re.fullmatch(r"[1-9][0-9]*", counter):
        raise ValueError("The shared action must return a positive integer counter")
    source = chart.read_text()
    metadata = yaml.safe_load(source)
    expected = f"{metadata['name']}-{counter}.0.0"
    if tag != expected:
        raise ValueError(f"Expected native suffixed release tag {expected}, got {tag}; update the shared version action first")
    updated, count = re.subn(r"^version:[^\n]*$", f"version: {counter}.0.0", source, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("Chart metadata must have exactly one root version field")
    chart.write_text(updated)
    print(f"{metadata['name']}: {counter}.0.0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chart", type=Path)
    parser.add_argument("counter")
    parser.add_argument("tag")
    args = parser.parse_args()
    try:
        update(args.chart, args.counter, args.tag)
    except (ValueError, yaml.YAMLError) as error:
        parser.exit(1, f"Chart version update failed: {error}\n")
