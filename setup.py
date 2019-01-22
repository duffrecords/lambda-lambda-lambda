#!/usr/bin/env python

import argparse
import awscli
import boto3
import json
import os
import sys
import zipfile
from base64 import b64decode
from configparser import ConfigParser
from distutils.version import LooseVersion
from pip._internal import main as pip
from shutil import rmtree

if LooseVersion(awscli.__version__) < LooseVersion('1.9.57'):
    sys.exit('AWS CLI version 1.9.57 or greater is required')

deploy_files = ["build_package.sh", "install_requirements.sh", "lambda_function.py", "setup_git.sh"]

configparser = ConfigParser()
configparser.read('config.ini')
git_email = configparser.get('github', 'git_email')
git_token = configparser.get('github', 'git_token')
git_username = configparser.get('github', 'git_username')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--init', action='store_true', help='')
parser.add_argument('--bucket', required=True, help='S3 bucket for storing deployment packages')
parser.add_argument('--function', default='lambda-lambda-lambda', help='name of Lambda function')
parser.add_argument('--region', help='AWS region in which Lambda function is located')
args = parser.parse_args()

if args.region:
    region = args.region
else:
    session = boto3.session.Session()
    region = session.region_name
iam_client = boto3.client('iam')
lambda_client = boto3.client('lambda', region_name=region)
s3_client = boto3.client('s3', region_name=region)

print('creating deployment package')
package = 'lambda-function.zip'
with zipfile.ZipFile(package, mode='w', compression=zipfile.ZIP_DEFLATED) as f:
    for file in deploy_files:
        f.write(file)

print('uploading deployment package to S3')
s3_client.upload_file(package, args.bucket, f'{args.function}/{package}')

policy_document = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "Service": ["lambda.amazonaws.com"]
        },
        "Action": ["sts:AssumeRole"]
    }]
}

try:
    # check if IAM role exists
    iam_client.get_role(RoleName=args.function)
except iam_client.exceptions.NoSuchEntityException:
    print(f'creating {args.function} IAM role')
    response = iam_client.create_role(
        Path='/service-role/',
        RoleName=args.function,
        AssumeRolePolicyDocument=json.dumps(policy_document),
        Description='allows Lambda function access to S3 and CloudWatch logs',
        MaxSessionDuration=3600
    )
    if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
        sys.exit(response)
    response = iam_client.attach_role_policy(
        RoleName=args.function,
        PolicyArn=f'arn:aws:iam::aws:policy/AWSLambdaFullAccess'
    )
    if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
        sys.exit(response)
try:
    role = iam_client.get_role(RoleName=args.function)
except iam_client.exceptions.NoSuchEntityException:
    sys.exit(f'cannot find ARN for {args.function} role')

try:
    function_exists = lambda_client.get_function(FunctionName=args.function)
except lambda_client.exceptions.ResourceNotFoundException:
    function_exists = False

if function_exists:
    print(f'updating {args.function} with latest code')
    response = lambda_client.update_function_code(
        FunctionName=args.function,
        S3Bucket=args.bucket,
        S3Key=f'{args.function}/{package}'
    )
else:
    print(f'creating {args.function} Lambda function')
    response = lambda_client.create_function(
        FunctionName=args.function,
        Runtime='python3.6',
        Role=role['Role']['Arn'],
        Handler='lambda_function.lambda_handler',
        Code={
            'S3Bucket': args.bucket,
            'S3Key': f'{args.function}/{package}'
        },
        Description='a Lambda function that can build and deploy other Lambda functions',
        Timeout=60,
        MemorySize=2048,
        Environment={
            'Variables': {
                'deploy_bucket': args.bucket,
                'git_email': git_email,
                'git_token': git_token,
                'git_username': git_username
            }
        },
    )
    if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
        sys.exit(response)

if args.init:
    print('installing build prerequisites')
    try:
        rmtree('build_layer')
    except FileNotFoundError:
        pass
    os.makedirs('build_layer/python')
    placeholder_text = '# placeholder until actual module is installed in Lambda environment\n'
    for dir in ['dulwich', 'yaml']:
        os.makedirs(f'build_layer/python/{dir}')
        with open(f'build_layer/python/{dir}/__init__.py', 'w+') as f:
            f.write(placeholder_text)
    with open('build_layer/python/dulwich/porcelain.py', 'w+') as f:
        f.write(placeholder_text)
    pip(['--no-cache-dir', 'install', 'boto3', '-t', 'build_layer/python/'])
    archive = 'build_layer/python/build-env.zip'
    with zipfile.ZipFile(archive, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as f:
        print('creating archive')
        length = len('build_layer')
        for root, dirs, files in os.walk('build_layer'):
            folder = root[length:]  # path without "parent"
            for file in files:
                if not file.endswith('.pyc'):
                    f.write(os.path.join(root, file), os.path.join(folder, file))
    print(f'uploading build-env layer')
    with open(archive, 'rb') as f:
        archive_content = f.read()
    response = lambda_client.publish_layer_version(
        LayerName='build-env',
        Description='placeholder layer until Dulwich and PyYAML are built',
        Content={
            'ZipFile': archive_content
        },
    )
    layer_arn = response['LayerVersionArn']
    # print(json.dumps(response, indent=4))
    print(f'updating {args.function} with build layer')
    arn = response['LayerVersionArn']
    response = lambda_client.update_function_configuration(
            FunctionName=args.function,
            Layers=[layer_arn]
    )

print(f'invoking {args.function} to build Dulwich and PyYAML')
response = lambda_client.invoke(
    FunctionName=args.function,
    InvocationType='RequestResponse',
    LogType='Tail',
    Payload=json.dumps({
        "function": args.function,
        "action": "setup"
    })
)
print(b64decode(response['ResponseMetadata']['HTTPHeaders']['x-amz-log-result']).decode())
