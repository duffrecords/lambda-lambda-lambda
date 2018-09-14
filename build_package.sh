#!/bin/bash

repo_name="$1"

cd "/tmp/${repo_name}"
echo "$(date) copying modules from virtualenv to build directory..."
rm -rf /tmp/build
mkdir -p /tmp/build
shopt -s dotglob
cd venv/lib/python3.*/site-packages
cp -r . /tmp/build/
cd "/tmp/${repo_name}"
for i in $(ls venv/src); do
  if [ -d venv/src/${i} ]; then
    if [ -f venv/src/${i}/setup.py ]; then
      package=$(grep packages= venv/src/${i}/setup.py | cut -d\' -f2)
      cp -r venv/src/${i}/${package} /tmp/build
    fi
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
ls -hl /tmp/build
