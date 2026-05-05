#!/bin/bash

rm -rf out
mkdir -p out
helm template \
    --namespace demo-namespace1 \
    --set password=redis \
    demo-redis1 \
    ./charts/redis > out/redis.yaml
