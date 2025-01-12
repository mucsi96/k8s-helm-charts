#!/bin/bash
set -e

if [[ "$OSTYPE" == "darwin"* ]]; then
    brew update && brew upgrade && brew install kubernetes-cli
fi

if [[ "$OSTYPE" == "linux-gnu" ]]; then
    if ! command -v kubectl &> /dev/null; then
        echo "kubectl is not installed. Please install kubectl and try again."
        exit 1
    fi

    if ! command -v helm &> /dev/null; then
        echo "helm is not installed. Please install helm and try again."
        exit 1
    fi
fi

pip install --upgrade pip

pip install -r requirements.txt

helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts