#!/usr/bin/env python3

from os import environ, makedirs
from subprocess import run
from pathlib import Path
import sys
from textwrap import dedent
from publish_tools import version_utils, github_utils

root_directory = Path(__file__).parent.parent

makedirs(root_directory / "dist", exist_ok=True)

for package in [
    {"tag-prefix": "client-app", "src": root_directory / "charts/client_app"},
]:
    version = version_utils.get_version(
        src=package["src"], tag_prefix=package["tag-prefix"]
    )
    
    with open(package["src"] / "Chart.yaml", "r") as file:
        chart_yaml = file.read()
        chart_yaml = chart_yaml.replace("version: 0.1.0", f"version: {version}.0.0")
        
    with open(package["src"] / "Chart.yaml", "w") as file:
        file.write(chart_yaml)

    run(
        [
            "helm",
            "package",
            package["src"],
            "--destination",
            "dist",
        ],
        cwd=root_directory,
        check=True,
    )
    github_utils.create_release(
        tag_prefix=package["tag-prefix"],
        version=version,
        access_token=sys.argv[1],
        body=dedent(
            f"""
            [Helm chart](https://mucsi96.github.io/k8s-helm-charts/{package["tag-prefix"]}-{version}.0.0.tgz)

            ```bash
                helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts
                helm install mucsi96/{package["tag-prefix"]} --version {version}.0.0
            ```
        """
        ),
    )


github_utils.create_pages_artifact(directory=root_directory / "dist")
