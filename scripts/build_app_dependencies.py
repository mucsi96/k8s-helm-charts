"""Bundle the pinned local library into each independently released app chart."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
APP_CHARTS = ['client_app', 'spring_app', 'go_app', 'node_app', 'rust_app']


def main():
    for name in APP_CHARTS:
        subprocess.run(['helm', 'dependency', 'build', '--skip-refresh', str(ROOT / 'charts' / name)], check=True)


if __name__ == '__main__':
    main()
