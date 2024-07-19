#!/bin/bash

brew update && brew upgrade && brew install kubernetes-cli

pip install --upgrade pip

pip install -r requirements.txt