#!/bin/bash

FUNCTION="$(basename $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd ))"
FILES="build_package.sh install_requirements.sh lambda_function.py setup_git.sh"

AWS_PROFILE=$(grep aws_profile config.ini | sed 's/.* = //')
AWS_REGION=$(grep aws_region config.ini | sed 's/.* = //')
export AWS_ACCESS_KEY_ID="$(aws --profile "$AWS_PROFILE" configure get aws_access_key_id)"
if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
    echo "Could not determine AWS_ACCESS_KEY_ID"
    exit 1
fi
export AWS_SECRET_ACCESS_KEY="$(aws --profile "$AWS_PROFILE" configure get aws_secret_access_key)"
if [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "Could not determine AWS_SECRET_ACCESS_KEY"
    exit 1
fi
BUCKET=$(grep deployment_bucket config.ini | sed 's/.* = //')
if [[ -z $BUCKET ]]; then
    echo "'deployment_bucket' not defined in config.ini"
    exit 1
fi

zip -9qyr package.zip $FILES
aws s3api put-object --bucket $BUCKET --key "${FUNCTION}/package.zip" --body package.zip --server-side-encryption AES256
aws --region $AWS_REGION lambda update-function-code --function-name $FUNCTION --s3-bucket $BUCKET --s3-key ${FUNCTION}/package.zip
