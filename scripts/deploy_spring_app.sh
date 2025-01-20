#!/bin/bash

host=$(az keyvault secret show --vault-name p05 --name hostname --query value --output tsv)
blobStorageEndpointUrl=$(az storage account show --name ibari --resource-group ibari --query "primaryEndpoints.blob" --output tsv)

helm upgrade postgres-azure-backup ./charts/spring_app \
    --install \
    --force \
    --kubeconfig .kube/config \
    --namespace demo \
    --set image=mucsi96/postgres-azure-backup:12 \
    --set host=backup.$host \
    --set serviceAccountName=backup-app \
    --set env.BLOBSTORAGE_ENDPOINT_URL=$blobStorageEndpointUrl \
    --set env.DATABASES_CONFIG_PATH=/app/databases_config.json \
    --set configFile[0].name=databases_config.json \
    --set configFile[0].mountPath=/app/databases_config.json \
    --set "configFile[0].data=$(cat scripts/databases_config.json | base64)" \
    --wait