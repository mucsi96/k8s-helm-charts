#!/bin/bash

brew update && brew upgrade && brew install kubernetes-cli

pip install --upgrade pip

pip install -r requirements.txt

helm repo add mucsi96 https://mucsi96.github.io/k8s-helm-charts