#!/bin/bash

rm -rf out
mkdir -p out
helm template \
    --namespace demo-namespace1 \
    --set name=demo \
    --set username=postgres \
    --set password=postgres \
    --set exporterUsername=exporter \
    --set exporterPassword=exporter \
    demo-db1 \
    ./charts/postgres_db > out/postgres-db.yaml