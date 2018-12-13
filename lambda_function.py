#!/usr/bin/env python

import boto3
import os
import re
import subprocess
import zipfile

s3_client = boto3.client('s3', region_name=os.environ['AWS_REGION'])
lambda_client = boto3.client('lambda', region_name=os.environ['AWS_REGION'])


def shell(command, pattern=''):
    found = False
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    for line in stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n'):
        if line:
            print(line)
            if pattern and pattern in line:
                found = True
    return True if found else False


def zipdir(path, package):
    with zipfile.ZipFile(package, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as f:
        length = len(path)
        for root, dirs, files in os.walk(path):
            folder = root[length:]  # path without "parent"
            for file in files:
                f.write(os.path.join(root, file), os.path.join(folder, file))


def lambda_handler(event, context):
    function = event['function']
    bucket = os.environ['deploy_bucket']
    task_root = os.environ['LAMBDA_TASK_ROOT']

    if event['action'] == 'setup':
        # install Dulwich since git is not available in Lambda
        result = shell(
            f"bash {task_root}/setup_git.sh",
            pattern='Successfully installed dulwich'
        )
        if not result:
            return {'status': 500, 'message': 'Failed to install Dulwich'}

    elif event['action'] == 'build':
        repo_name = event['repo_name']
        username = os.environ['git_username']
        token = os.environ['git_token']
        github_url = f'https://{token}:x-oauth-basic@github.com/{username}/{repo_name}.git'
        # build and deploy function
        from dulwich import porcelain, index, repo
        # os.chdir('/tmp')
        print(f"cloning {repo_name}...")
        try:
            porcelain.clone(github_url, f'/tmp/{repo_name}')
        except FileExistsError:
            porcelain.pull(f'/tmp/{repo_name}', github_url)
        branch = event.get('branch', '')
        if branch:
            refspec = f'refs/heads/{branch}'.encode()
            porcelain.pull(f'/tmp/{repo_name}', github_url, refspecs=[refspec])
            branch = refspec = ''
        print('checking for editable packages in requirements.txt')
        with open(f'/tmp/{repo_name}/requirements.txt') as f:
            requirements = f.readlines()
        editable = [r.strip('\n').split()[1] for r in requirements if r.startswith('-e')]
        print(f"installing requirements")
        shell(f"bash {task_root}/install_requirements.sh {repo_name}")
        for repo_url in editable:
            match = re.match(r'\w+\+(\w+:\/\/[\w\.]+\/[\w\-]+\/[\w\-]+)(@[\w\-]+|)(#egg=.*|)', repo_url)
            try:
                repo_url = match.group(1).rstrip('.git') + '.git'
            except IndexError:
                pass
            try:
                branch = match.group(2).lstrip('@')
            except IndexError:
                branch = ''
            try:
                module_name = match.group(3).lstrip('#egg=').lower()
            except IndexError:
                module_name = ''
            print(repo_url)
            try:
                if repo_url.split('/')[3] == username:
                    repo_url = repo_url.replace('://', f'://{token}:x-oauth-basic@')
            except IndexError:
                pass
            src_dir = f'/tmp/{repo_name}/venv/src/{module_name}'
            print(f"cloning {repo_url}...")
            try:
                porcelain.clone(repo_url, src_dir)
            except FileExistsError:
                porcelain.pull(src_dir, repo_url)
            if branch:
                refspec = f'refs/heads/{branch}'.encode()
                porcelain.pull(src_dir, repo_url, refspecs=[refspec])
        print(f"building {function} package")
        shell(f"bash {task_root}/build_package.sh {repo_name}")

    print('archiving package...')
    zipdir('/tmp/build', '/tmp/package.zip')
    print('uploading package to S3...')
    s3_client.upload_file('/tmp/package.zip', bucket, f'{function}/package.zip')
    print('updating Lambda function...')
    response = lambda_client.update_function_code(
        FunctionName=function,
        S3Bucket=bucket,
        S3Key=f'{function}/package.zip',
    )
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return {'status': 200, 'message': 'Success'}
    else:
        return {'status': 500, 'message': 'Failed to update Lambda function'}
