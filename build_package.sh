#!/bin/bash

repo_name="$1"

cd "/tmp/${repo_name}"
echo "$(date) creating virtualenv..."
python3 -m venv venv
source venv/bin/activate
# separate editable packages
mkdir -p venv/src
rm -rf venv/src/*
echo "$(date) downloading editable packages..."
grep '^\-e' requirements.txt | cut -d' ' -f2 | xargs python "/var/task/git_clone.py"
# exclude vendored, testing, and documentation modules
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
# sed -i '/^python-dateutil/d' requirements.txt
sed -i '/^s3transfer/d' requirements.txt
sed -i '/^setuptools/d' requirements.txt
sed -i '/^[sS]phinx/d' requirements.txt
sed -i '/^termcolor/d' requirements.txt
sed -i '/^WebTest/d' requirements.txt
echo "$(date) installing dependencies..."
pip install -r requirements.txt
echo "$(date) copying modules from virtualenv to build directory..."
rm -rf /tmp/build
mkdir -p /tmp/build
shopt -s dotglob
cd venv/lib/python3.*/site-packages
cp -r . /tmp/build/
cd "/tmp/${repo_name}"
for i in $(find venv/src -type d -depth 1); do
  if [ -f ${i}/setup.py ]; then
    package=$(grep packages= ${i}/setup.py | cut -d\' -f2)
    cp -r ${i}/${package} /tmp/build
  fi
done
echo "$(date) removing unnecessary files..."
find /tmp/build/ \( -name "*.pyc" -or -name "*.zip" \) -exec rm -rf {} \;
echo "$(date) copying application files to build directory..."
if [ -f files_to_deploy.sh ]; then
  bash files_to_deploy.sh /tmp/build
elif [ -f lambda_function.py ]; then
  cp lambda_function.py /tmp/build
fi
# zip -9qyr package.zip .
# ls -hl /tmp/build
deactivate
