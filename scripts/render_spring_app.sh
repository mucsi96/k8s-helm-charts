#!/bin/bash

rm -rf out
mkdir -p out
helm template demo-application1 ./charts/spring_app  \
    --namespace demo-namespace1 \
    --set image=mucsi96/postgres-azure-backup \
    --set host=demo.$host \
    --set basePath=/db \
    --set env.BLOBSTORAGE_ENDPOINT_URL=https://ibari.blob.core.windows.net \
    --set env.DATABASES_CONFIG_PATH=/app/databases_config.json \
    --set configFile[0].name=databases_config.json \
    --set configFile[0].mountPath=/app/databases_config.json \
    --set "configFile[0].data=$(cat scripts/databases_config.json | base64)" \
    > out/spring-app.yaml