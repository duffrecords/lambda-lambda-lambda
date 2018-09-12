#!/bin/bash

cd /tmp
echo "creating virtualenv..."
python3 -m venv venv
source venv/bin/activate
echo "installing dependencies..."
pip install urllib3 certifi
# dependencies above must be installed before using the --pure option
pip install dulwich --global-option="--pure"
deactivate
echo "copying modules from virtualenv to build directory"
mkdir -p build
shopt -s dotglob
mv venv/lib/python3.6/site-packages/* /tmp/build/
cp /var/task/*.py /var/task/*.sh /tmp/build/
# ls -hl /tmp/build/
# zip -9qyr gitpython.zip .
