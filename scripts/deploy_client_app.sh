#!/bin/bash

host=$(az keyvault secret show --vault-name p02 --name dns-zone --query value --output tsv)

helm install \
    --kubeconfig .kube/config \
    --namespace demo \
    --set image=mucsi96/hello-client \
    --set host=demo.$host \
    --set basePath=/ \
    --wait \
    demo \
    ./charts/client_app