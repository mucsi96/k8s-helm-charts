#!/bin/bash

rm -rf out
mkdir -p out
helm template \
    --namespace demo-namespace1 \
    --set-string config="logging { level = \"info\" }" \
    demo-alloy1 \
    ./charts/grafana_alloy > out/grafana-alloy.yaml
