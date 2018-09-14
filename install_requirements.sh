#!/bin/bash

repo_name="$1"

cd "/tmp/${repo_name}"
echo "$(date) creating virtualenv..."
python3 -m venv venv
source venv/bin/activate
# separate editable packages
mkdir -p venv/src
rm -rf venv/src/*
# exclude editable, vendored, testing, and documentation modules
sed -i '/^-e/d' requirements.txt
sed -i '/^alabaster/d' requirements.txt
sed -i '/^autodoc/d' requirements.txt
sed -i '/^apilogs/d' requirements.txt
sed -i '/^awslogs/d' requirements.txt
sed -i '/^Babel/d' requirements.txt
sed -i '/^boto/d' requirements.txt
sed -i '/^colored==/d' requirements.txt
sed -i '/^docutils/d' requirements.txt
sed -i '/^flake8/d' requirements.txt
sed -i '/^jmespath/d' requirements.txt
sed -i '/^mccabe/d' requirements.txt
sed -i '/^pip/d' requirements.txt
sed -i '/^pycodestyle/d' requirements.txt
sed -i '/^pyflakes/d' requirements.txt
sed -i '/^Pygments/d' requirements.txt
sed -i '/^s3transfer/d' requirements.txt
sed -i '/^setuptools/d' requirements.txt
sed -i '/^[sS]phinx/d' requirements.txt
sed -i '/^termcolor/d' requirements.txt
sed -i '/^WebTest/d' requirements.txt
echo "$(date) installing dependencies..."
pip install -r requirements.txt
deactivate
