#!/bin/bash

# default values
CONFIG_FILE="config.ini"
BRANCH="master"
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    FUNCTION="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
    SOURCE="$( readlink "$SOURCE" )"
    [[ $SOURCE != /* ]] && SOURCE="${FUNCTION}/${SOURCE}"
done
FUNCTION="$(basename "$( cd -P "$( dirname "$SOURCE" )" && pwd )")"
REPO="$FUNCTION"
LOG_FILE="deploy.log"
PROMPT=true
TIME=
VERSION=

usage() {
    echo "Usage: $0 [ -b GIT_BRANCH ] [ -c CONFIG_FILE ] [ -f FUNCTION_NAME ] [ -g GIT_REPO ] [ -l LOG_FILE] [ -p AWS_PROFILE ] [ -r AWS_REGION ] [ -t ] [ -v \"version description\" ][ -y ] [function|dependencieslayer]" 1>&2
}

exit_abnormal() {
    usage
    exit 1
}

# parse command line arguments
args=$(getopt b:c:f:g:l:p:r:ty $* > /dev/null 2>&1)
[ $? -ne 0 ] && exit_abnormal
eval set -- "$args"
while true; do
    case "$1" in
        -b)
            BRANCH=$2; shift 2 ;;
        -c)
            CONFIG_FILE=$2; shift 2 ;;
        -f)
            FUNCTION=$2; shift 2 ;;
        -g)
            REPO=$2; shift 2 ;;
        -l)
            LOG_FILE=$2; shift 2 ;;
        -p)
            AWS_PROFILE=$2; shift 2 ;;
        -r)
            AWS_REGION=$2; shift 2 ;;
        -t)
            TIME="time"; shift ;;
        -v)
            VERSION=", \"version\": \"$2\""; shift 2 ;;
        -y)
            PROMPT=false; shift ;;
        --) shift; break;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

# override default parameters, using config file
if [[ "$args" != *" -f"* ]]; then
    TEMP="$(grep -i FUNCTION_NAME $CONFIG_FILE | sed 's/.* = //')"
    [ ! -z "$TEMP" ] && FUNCTION="$TEMP"
fi
if [[ "$args" != *" -g"* ]]; then
    TEMP="$(grep -i GIT_REPO $CONFIG_FILE | sed 's/.* = //')"
    [ ! -z "$TEMP" ] && REPO="$TEMP"
fi
if [[ "$args" != *" -b"* ]]; then
    TEMP="$(grep -i GIT_BRANCH $CONFIG_FILE | sed 's/.* = //')"
    [ ! -z "$TEMP" ] && BRANCH="$TEMP"
fi
if [[ "$args" != *" -l"* ]]; then
    TEMP="$(grep -i LOG_FILE $CONFIG_FILE | sed 's/.* = //')"
    [ ! -z "$TEMP" ] && LOG_FILE="$TEMP"
fi
if [[ "$args" != *" -y"* ]]; then
    TEMP="$(grep -i PROMPT_BEFORE_DEPLOY $CONFIG_FILE | sed 's/.* = //' | tr '[:upper:]' '[:lower:]')"
    [ ! -z "$TEMP" ] && PROMPT="$TEMP"
fi
if [[ -z "$AWS_PROFILE" ]]; then
    AWS_PROFILE="$(grep -i AWS_PROFILE $CONFIG_FILE | sed 's/.* = //')"
    if [[ -z "$AWS_PROFILE" ]]; then
        echo "Please set the environment variable AWS_PROFILE or define it in $CONFIG_FILE"
        echo "    e.g. export AWS_PROFILE=\"my_profile_name\""
        exit 1
    fi
fi
if [[ -z "$AWS_REGION" ]]; then
    AWS_REGION="$(grep -i AWS_REGION $CONFIG_FILE | sed 's/.* = //')"
    if [[ -z "$AWS_REGION" ]]; then
      echo "Please set AWS_REGION as an environment variable or define it in $CONFIG_FILE"
    fi
fi

# ask user to confirm action
if [ ! -z "$*" ]; then
    ACTION="build $*"
    LAYERS="$*"
else
    ACTION="build"
    LAYERS="all"
fi
echo -e "The following will be built and deployed:\n"
echo "      LAYERS $LAYERS"
echo "      SOURCE ${REPO}:${BRANCH}"
echo " DESTINATION arn:aws:lambda:${AWS_REGION}:${AWS_PROFILE}:function:${FUNCTION}"
if [[ "$PROMPT" == "true" ]]; then
    echo -n -e "\nProceed? (y/n)  "
    read yn
    if [[ "$yn" != "y" ]]; then
        echo "Aborted"
    fi
fi

# check for jq, which is not installed by default
if which jq > /dev/null 2>&1; then
    JQ="$(which jq) -r .'LogResult'"
    kernel="$(uname -s)"
    if [[ "$kernel" == "Linux" ]]; then
        d="-d"
    elif [[ "$kernel" == "Darwin" ]]; then
        d="-D"
    fi
    B64="$(which base64) $d"
else
    echo "In order to parse and decode the log output, you need to install the 'jq' and 'base64' utilities."
    JQ=$(which tee)
    B64=$(which tee)
fi

# build and deploy the Lambda function
$TIME aws lambda invoke \
    --invocation-type RequestResponse \
    --function-name lambda-lambda-lambda \
    --region $AWS_REGION \
    --log-type Tail \
    --payload "{\"action\": \"${ACTION}\", \"branch\": \"${BRANCH}\", \"function\": \"${FUNCTION}\", \"repo_name\": \"${REPO}\"${VERSION}}" \
    --profile $AWS_PROFILE \
    $LOG_FILE | eval $JQ | eval $B64
