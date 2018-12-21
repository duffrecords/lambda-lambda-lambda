#!/bin/bash

runtime="$(echo $AWS_EXECUTION_ENV | sed 's/AWS_Lambda_//')"
if [ -z $runtime ]; then
  echo "could not determine runtime"
  exit 1
fi
cd /tmp || exit 1
rm -rf build
mkdir -p build/python
echo "creating virtualenv..."
$runtime -m venv venv
source venv/bin/activate
pip --no-cache-dir install --upgrade pip
base_virtualenv_files="$(ls venv/lib/${runtime}/site-packages)"
echo "installing dependencies..."
pip --no-cache-dir install urllib3 certifi PyYAML
# dependencies above must be installed before using the --pure option
pip --no-cache-dir install dulwich --global-option="--pure"
deactivate
echo "copying modules from virtualenv to build directory"
shopt -s dotglob
mv venv/lib/${runtime}/site-packages/* /tmp/build/python/
for file in $base_virtualenv_files; do
  rm -rf /tmp/build/python/${file}
done
cp -a /opt/python/boto* /tmp/build/python/
# delete documentation and tests since they won't be used in Lambda environment
rm -rf /tmp/build/python/docs
rm -rf /tmp/build/python/dulwich/tests
# cp /var/task/*.py /var/task/*.sh /tmp/build/
