#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
helm template demo-go-app "$PROJECT_DIR/charts/go_app" \
    --namespace demo-namespace \
    --set image=example/go-app:1 \
    --set host=api.example.com \
    --set basePath=/api \
    --set serviceAccountName=demo-go-app \
    --set clientId=12345678-1234-1234-1234-123456789abc
