#!/bin/bash

runtime="$(echo $AWS_EXECUTION_ENV | sed 's/AWS_Lambda_//')"
repo_name="$1"
requirements="$2"
if [ ! -d "/tmp/${repo_name}" ]; then
  echo "/tmp/${repo_name} does not exist"
  exit 1
fi
if [ ! -f "/tmp/${repo_name}/${requirements}" ]; then
  echo "/tmp/${repo_name}/${requirements} does not exist"
  exit 1
fi

cd "/tmp/${repo_name}" || exit
rm -rf venv
echo "$(date) creating virtualenv..."
echo "$(python --version)"
python -m venv venv
source venv/bin/activate
pip install --no-cache-dir --upgrade pip
base_virtualenv_files="$(ls venv/lib/${runtime}/site-packages)"
# separate editable packages
mkdir -p venv/src
rm -rf venv/src/*
# exclude editable, vendored, testing, and documentation modules
sed -i '/^-e/d' "$requirements"
sed -i '/^alabaster/d' "$requirements"
sed -i '/^autodoc/d' "$requirements"
sed -i '/^apilogs/d' "$requirements"
sed -i '/^awslogs/d' "$requirements"
sed -i '/^Babel/d' "$requirements"
sed -i '/^boto/d' "$requirements"
sed -i '/^colored==/d' "$requirements"
sed -i '/^docutils/d' "$requirements"
sed -i '/^flake8/d' "$requirements"
sed -i '/^jmespath/d' "$requirements"
sed -i '/^mccabe/d' "$requirements"
sed -i '/^pip/d' "$requirements"
sed -i '/^pycodestyle/d' "$requirements"
sed -i '/^pyflakes/d' "$requirements"
sed -i '/^Pygments/d' "$requirements"
sed -i '/^s3transfer/d' "$requirements"
sed -i '/^setuptools/d' "$requirements"
sed -i '/^[sS]phinx/d' "$requirements"
sed -i '/^termcolor/d' "$requirements"
sed -i '/^WebTest/d' "$requirements"
echo "$(date) installing dependencies..."
pip --no-cache-dir install -r "$requirements"
deactivate
cd "venv/lib/${runtime}/site-packages/" || exit
cp -a . /tmp/build/python/
# delete modules that were not explicitly listed in requirements.txt, to minimize layer size
for file in $base_virtualenv_files; do
  rm -rf /tmp/build/python/${file}
done
