#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
helm template demo-rust-app "$PROJECT_DIR/charts/rust_app" \
    --namespace demo-namespace \
    --set image=example/rust-app:1 \
    --set host=rust.example.com \
    --set env.RUST_LOG=info \
    --set-json 'routeFilters=[{"type":"ResponseHeaderModifier","responseHeaderModifier":{"set":[{"name":"Cache-Control","value":"no-store"}]}}]'
