#!/bin/bash

rm -rf out
mkdir -p out
helm template \
    --namespace demo-namespace1 \
    --set image=mucsi96/hello-server \
    --set host=demo.example.com \
    --set basePath=/ \
    --set env.ENV_VAR1=value1 \
    --set env.ENV_VAR2=value2 \
    --set configFile[0].name=application.json \
    --set configFile[0].mountPath=/config/application.json \
    --set "configFile[0].data=$(cat charts/spring_app/Chart.yaml)" \
    demo-application1 \
    ./charts/spring_app > out/spring-app.yaml