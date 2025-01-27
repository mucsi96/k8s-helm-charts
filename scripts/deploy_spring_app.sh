#!/bin/bash

host=$(az keyvault secret show --vault-name p05 --name hostname --query value --output tsv)
blobStorageEndpointUrl=$(az storage account show --name ibari --resource-group ibari --query "primaryEndpoints.blob" --output tsv)
apiClientId=$(az keyvault secret show --vault-name p05 --name backup-api-client-id --query value --output tsv)
spaClientId=$(az keyvault secret show --vault-name p05 --name backup-spa-client-id --query value --output tsv)

helm upgrade postgres-azure-backup ./charts/spring_app \
    --install \
    --force \
    --kubeconfig .kube/config \
    --namespace backup \
    --set image=mucsi96/postgres-azure-backup:18 \
    --set host=backup.$host \
    --set clientId=$apiClientId \
    --set serviceAccountName=postgres-azure-backup \
    --set env.BLOBSTORAGE_ENDPOINT_URL=$blobStorageEndpointUrl \
    --set env.DATABASES_CONFIG_PATH=/app/databases_config.json \
    --set env.UI_CLIENT_ID=$spaClientId \
    --set configFile[0].name=databases_config.json \
    --set configFile[0].mountPath=/app/databases_config.json \
    --set "configFile[0].data=$(cat scripts/databases_config.json | base64)" \
    --wait