"""Check dependency versions, portable packages and optional render equivalence."""
import argparse
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

import yaml
from build_app_dependencies import ROOT, APP_CHARTS


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout


def render(chart, values):
    result = subprocess.run(['helm', 'template', 'fixture', str(chart), '--namespace', 'fixture', '-f', '-'],
                            input=yaml.safe_dump(values), text=True, capture_output=True, check=True)
    return sorted((item for item in yaml.safe_load_all(result.stdout) if item),
                  key=lambda item: (item['kind'], item['metadata']['name']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', default='')
    parser.add_argument('--compare-ref')
    args = parser.parse_args()
    library = yaml.safe_load((ROOT / 'libraries/app_common/Chart.yaml').read_text())
    assert library['type'] == 'library'
    if args.base_ref and set(args.base_ref) != {'0'}:
        previous = subprocess.run(['git', 'show', f'{args.base_ref}:libraries/app_common/Chart.yaml'], cwd=ROOT, capture_output=True)
        if previous.returncode == 0:
            changed = git('diff', args.base_ref, '--', 'libraries/app_common/templates')
            assert not changed or yaml.safe_load(previous.stdout)['version'] != library['version'], 'Bump app-common and all consumer dependency versions when shared templates change'

    with tempfile.TemporaryDirectory(prefix='app-common-') as temporary:
        directory = Path(temporary)
        baseline = directory / 'baseline'
        if args.compare_ref:
            baseline.mkdir()
            paths = ['charts']
            if git('ls-tree', '--name-only', args.compare_ref, 'libraries/app_common'):
                paths.append('libraries/app_common')
            with tarfile.open(fileobj=io.BytesIO(git('archive', args.compare_ref, *paths))) as archive:
                archive.extractall(baseline, filter='data')
        for name in APP_CHARTS:
            chart = ROOT / 'charts' / name
            metadata = yaml.safe_load((chart / 'Chart.yaml').read_text())
            baseline_chart = baseline / 'charts' / name
            if args.compare_ref and baseline_chart.exists() and (baseline / 'libraries/app_common').exists():
                subprocess.run(['helm', 'dependency', 'build', '--skip-refresh', str(baseline / 'charts' / name)], capture_output=True, check=True)
            expected = {'name': library['name'], 'version': library['version'], 'repository': 'file://../../libraries/app_common'}
            assert metadata['dependencies'] == [expected]
            assert yaml.safe_load((chart / 'Chart.lock').read_text())['dependencies'] == [expected]
            subprocess.run(['helm', 'package', str(chart), '--destination', str(directory)], capture_output=True, check=True)
            package = directory / f'{metadata["name"]}-{metadata["version"]}.tgz'
            with tarfile.open(package) as archive:
                assert any('/charts/app-common/templates/' in item.name for item in archive), 'Published chart must bundle its shared templates'
            values = {'image': 'example/app:1', 'host': 'app.example.test', 'clientId': 'fixture', 'serviceAccountName': 'fixture'}
            if name == 'static_client_app':
                values = {'host': 'app.example.test', 'staticOrigin': 'fixture.z1.web.core.windows.net'}
            variants = [values]
            variants.extend({**values, 'auth': {'proxyService': 'fixture-proxy', 'mode': mode}} for mode in ['api-token', 'email-header', 'login-gate'])
            if name == 'client_app':
                variants.append({**variants[1], 'runtimeConfig': {'clientAppName': 'fixture', 'clientLogUrl': 'https://app.example.test/_telemetry/collect'}})
            elif name != 'static_client_app':
                variants.append({**variants[1], 'basePath': '/api/v1', 'appPort': 8090})
            for variant in variants:
                rendered = render(chart, variant)
                assert render(package, variant) == rendered, f'{name}: packaged chart changed behavior'
                if args.compare_ref and baseline_chart.exists():
                    assert render(baseline / 'charts' / name, variant) == rendered, f'{name}: refactor changed rendered resources'
    print('Shared library versions and all self-contained app packages verified' + ('; existing charts match baseline' if args.compare_ref else ''))


if __name__ == '__main__':
    main()
