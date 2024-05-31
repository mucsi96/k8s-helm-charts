#!/bin/bash

rm -rf out
mkdir -p out
helm template \
    --namespace demo-namespace1 \
    --set image=mucsi96/hello-client \
    --set host=demo.example.com \
    --set basePath=/ \
    --set env.ENV_VAR1=value1 \
    --set env.ENV_VAR2=value2 \
    demo-application1 \
    ./charts/client_app > out/client-app.yaml