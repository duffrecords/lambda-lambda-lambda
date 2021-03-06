#!/usr/bin/env python

import boto3
import errno
import os
import re
import subprocess
from shutil import copy, copytree, Error, rmtree
import zipfile

s3_client = boto3.client('s3', region_name=os.environ['AWS_REGION'])
lambda_client = boto3.client('lambda', region_name=os.environ['AWS_REGION'])
bucket = os.environ['deploy_bucket']
task_root = os.environ['LAMBDA_TASK_ROOT']
runtime = os.environ['AWS_EXECUTION_ENV'].replace('AWS_Lambda_', '')
git_url_regex = re.compile(r'\w+\+(\w+:\/\/[\w\.]+\/[\w\-]+\/[\w\-\.]+)@?((?<=@)[\w\-]+|)(#egg=.*|)')

layer_descriptions = {
    'function': 'Lambda function code',
    'dependencies': 'dependencies from requirements.txt',
    'build-env': 'dependencies for {} (Dulwich and PyYAML)'.format(os.environ['AWS_LAMBDA_FUNCTION_NAME'])
}


def shell(command, pattern=''):
    """ Runs an arbitrary shell command and optionally tests output for a particular string"""
    found = False
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    for line in stdout.decode('utf-8').split('\n') + stderr.decode('utf-8').split('\n'):
        if line:
            print(line)
            if pattern and pattern in line:
                found = True
    return True if found else False


def clean_build_dir(runtime_dir=False):
    """Removes and recreates build directory"""
    try:
        rmtree('/tmp/build')
    except FileNotFoundError:
        pass
    try:
        os.makedirs('/tmp/build/python')
    except FileExistsError:
        pass


def remove_empty_dirs(dirs):
    """Removes directories if they are empty"""
    if isinstance(dirs, str):
        dirs = [dirs]
    for dir in dirs:
        try:
            if not os.listdir(dir):
                rmtree(dir)
        except FileNotFoundError:
            pass


def zipdir(path, package):
    """Recursively archives a folder"""
    print(f'archiving contents of {path} into {package}')
    path_contents = os.listdir(path)
    for i, item in enumerate(path_contents):
        box_char = '└─' if i == len(path_contents) - 1 else '├─'
        trailing_slash = '/' if os.path.isdir(item) else ''
        print(f'{box_char} {item}{trailing_slash}')
        subdir = os.path.join(path, item)
        if os.path.isdir(subdir):
            subdir_contents = os.listdir(subdir)
            for j, file in enumerate(subdir_contents):
                box_char = '└─' if j == len(subdir_contents) - 1 else '├─'
                line_char = ' ' if i == len(path_contents) - 1 else '│'
                trailing_slash = '/' if os.path.isdir(file) else ''
                print(f'{line_char}  {box_char} {file}{trailing_slash}')
    with zipfile.ZipFile(package, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as f:
        length = len(path)
        for root, dirs, files in os.walk(path):
            folder = root[length:]  # path without "parent"
            for file in files:
                f.write(os.path.join(root, file), os.path.join(folder, file))


def publish_layer(function, layer, desc='', runtimes=[], license=''):
    """Publishes contents of build directory as a Lambda layer"""
    remove_empty_dirs('/tmp/build/python')
    if layer == 'dependencies':
        layer_name = f'{function}-dependencies'
    else:
        layer_name = layer
    archive = f'/tmp/{layer_name}.zip'
    zipdir('/tmp/build', archive)
    with open(archive, 'rb') as f:
        archive_content = f.read()
    if not desc:
        desc = layer_descriptions.get(layer_name, 'additional deployment files')
    params = {
        'LayerName': layer_name,
        'Description': desc,
        'Content': {'ZipFile': archive_content}
    }
    if runtimes:
        params['CompatibleRuntimes'] = runtimes
    if license:
        params['LicenseInfo'] = license
    print(f'publishing {layer_name} layer')
    response = lambda_client.publish_layer_version(**params)
    if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
        return None
    return response['LayerVersionArn']


def updated_layers(function, new_layers):
    new_layer_names = [arn.split(':')[-2] for arn in new_layers]
    response = lambda_client.get_function_configuration(FunctionName=function)
    existing_layers = [l['Arn'] for l in response.get('Layers', []) if not any(n in l['Arn'] for n in new_layer_names)]
    # TO DO: decide on a reasonable merge order strategy
    if existing_layers:
        return new_layers + existing_layers
    else:
        return new_layers


def lambda_handler(event, context):
    print('event: {}'.format(event))
    function = event['function']

    if event['action'] == 'setup':
        # install Dulwich since git is not available in Lambda
        clean_build_dir()
        result = shell(
            f"bash {task_root}/setup_git.sh",
            pattern='Successfully installed dulwich'
        )
        if not result:
            return {'status': 500, 'message': 'Failed to install Dulwich and PyYAML'}
        layer_version_arn = publish_layer(
            os.environ['AWS_LAMBDA_FUNCTION_NAME'],
            'build-env',
            runtimes=[runtime],
            license='Apache-2.0/GPL-2.0-or-later/MIT'
        )
        if not layer_version_arn:
            return {'statusCode': 500, 'body': 'Failed to publish layer'}
        response = lambda_client.update_function_configuration(
                FunctionName=function,
                Layers=updated_layers(function, [layer_version_arn])
        )
        if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
            return {'statusCode': 500, 'body': 'Failed to update function configuration'}
        else:
            return {'statusCode': 200, 'body': 'Success'}

    elif event['action'].startswith('build'):
        layer_versions = []
        from dulwich import porcelain
        args = event['action'].split()
        components = ['all'] if len(args) == 1 else args[1:]
        repo_name = event['repo_name']
        username = os.environ['git_username']
        token = os.environ.get('git_token', '')
        if token:
            github_url = f'https://{token}:x-oauth-basic@github.com/{username}/{repo_name}.git'
        else:
            github_url = f'https://github.com/{username}/{repo_name}.git'
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
        print(os.listdir(task_root))
        print(os.listdir(f'/tmp/{repo_name}'))
        build_file = event.get('build_file', 'build.yaml')
        if build_file.endswith('.yaml'):
            from yaml import load
            with open(f'/tmp/{repo_name}/{build_file}', 'r') as f:
                build_config = load(f.read())
        elif build_file.endswith('.json'):
            import json
            with open(f'/tmp/{repo_name}/{build_file}', 'r') as f:
                build_config = json.loads(f.read())
        layers = build_config.get('layers', {})

        # package dependencies layer
        if components == ['all'] or 'dependencies' in components:
            clean_build_dir()
            for dependency_file in layers.get('dependencies', []):
                print(f'checking for editable packages in {dependency_file}')
                with open(f'/tmp/{repo_name}/{dependency_file}') as f:
                    requirements = f.readlines()
                editable = [r.strip('\n').split()[1] for r in requirements if r.startswith('-e')]
                print(f"installing requirements")
                shell(f"bash {task_root}/install_requirements.sh {repo_name} {dependency_file}")
                for repo_url in editable:
                    match = git_url_regex.match(repo_url)
                    branch = module_name = ''
                    if match and match.group(1):
                        repo_url = match.group(1).rstrip('.git') + '.git'
                        branch = match.group(2).lstrip('@')
                        if match.group(3):
                            egg_name = match.group(3).lstrip('#egg=').replace('-', '_')
                            module_name = egg_name.lower().replace('_', '-')
                            module_dirs = [egg_name.lower(), f'{egg_name}.egg-info']
                        else:
                            module_name = repo_url.split('/')[-1]
                            module_dirs = [module_name.replace('-', '_')]
                    else:
                        print(f'could not parse {repo_url}')
                        continue
                    print(repo_url)
                    try:
                        if (repo_url.split('/')[3] == username) and token:
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
                    for module_dir in module_dirs:
                        print('copying {} to {}'.format(f'{src_dir}/{module_dir}', f'/tmp/build/python/{module_dir}'))
                        try:
                            copytree(f'{src_dir}/{module_dir}', f'/tmp/build/python/{module_dir}')
                        except (Error, OSError) as e:
                            print('Directory not copied. Error: %s' % e)
            layer_version_arn = publish_layer(
                function,
                'dependencies',
                runtimes=build_config['function'].get('runtimes', []),
                license=build_config['function'].get('license', [])
            )
            if not layer_version_arn:
                return {'statusCode': 500, 'body': 'Failed to publish layer'}
            layer_versions.append(layer_version_arn)

        # package user-defined layers
        if components == ['all'] or any(c not in ['function', 'dependencies', 'all'] for c in components):
            clean_build_dir()
            for layer, attr in layers.items():
                if layer in ['function', 'dependencies', 'all']:
                    continue
                print(f'building {layer} layer')
                commands = attr.get('preinstall', [])
                if commands:
                    os.chdir(f'/tmp/{repo_name}')
                    for command in commands:
                        print(command)
                        if any(command.startswith(p) for p in ['python', 'pip']):
                            shell(f'source /tmp/{repo_name}/venv/bin/activate; {command}; deactivate')
                        else:
                            shell(f'bash -c "{command}"')
                print('{}:\n{}'.format(repo_name, os.listdir(f'/tmp/{repo_name}')))
                source_dir = attr.get('source_dir', '')
                dest_dir = attr.get('dest_dir', '')
                if not os.path.isdir(os.path.join(f'/tmp/{repo_name}', dest_dir)):
                    os.mkdir(os.path.join(f'/tmp/{repo_name}', dest_dir))
                for file in attr.get('files', []):
                    src = os.path.join(f'/tmp/{repo_name}', source_dir, file)
                    if os.path.isdir(src):
                        dst = os.path.join(f'/tmp/build', dest_dir, file)
                        print('copying {} to {}'.format(src, dst))
                        copytree(src, dst)
                    else:
                        dst = os.path.join(f'/tmp/build/', dest_dir)
                        print('copying {} to {}'.format(src, dst))
                        copy(src, dst)
                layer_version_arn = publish_layer(
                    function,
                    layer,
                    runtimes=attr.get('runtimes', []),
                    license=attr.get('license', [])
                )
                if not layer_version_arn:
                    return {'statusCode': 500, 'body': 'Failed to publish layer'}
                layer_versions.append(layer_version_arn)

        if layer_versions:
            print('updating function with the following layers:\n  {}'.format('\n  '.join(layer_versions)))
            response = lambda_client.update_function_configuration(
                    FunctionName=function,
                    Layers=updated_layers(function, layer_versions)
            )
            if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
                return {'statusCode': 500, 'body': 'Failed to update function configuration'}

        # package main function code
        if components == ['all'] or 'function' in components:
            print(f"building {function} package")
            clean_build_dir()
            # shell(f"bash {task_root}/build_package.sh {repo_name}")
            source_dir = build_config['function'].get('source_dir', '')
            for file in build_config['function']['files']:
                src = os.path.join(f'/tmp/{repo_name}', source_dir, file)
                if os.path.isdir(src):
                    dst = os.path.join(f'/tmp/build', file)
                    copytree(src, dst)
                else:
                    dst = f'/tmp/build/'
                    copy(src, dst)
            remove_empty_dirs('/tmp/build/python')
            archive = '/tmp/lambda_function.zip'
            zipdir('/tmp/build', archive)
            print('uploading package to S3...')
            key = f'{function}/lambda_function.zip'
            s3_client.upload_file(archive, bucket, key)
            print('updating Lambda function...')
            response = lambda_client.update_function_code(
                FunctionName=function,
                S3Bucket=bucket,
                S3Key=f'{function}/lambda_function.zip',
            )
            if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
                return {'statusCode': 500, 'body': 'Failed to update Lambda function code'}

            # update Lambda function version
            if event.get('version', False) == 'true':
                checksum = response['CodeSha256']
                response = lambda_client.publish_version(
                    FunctionName=function,
                    CodeSha256=checksum
                )
                if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
                    return {'statusCode': 500, 'body': 'Failed to update Lambda function version'}
                else:
                    print('updated Lambda function version to {}'.format(response['Version']))

            # create or update Lambda function alias
            if event.get('alias', ''):
                params = {'FunctionName': function, 'Name': event['alias']}
                if event.get('version', False) == 'true':
                    params['FunctionVersion'] = response['Version']
                try:
                    response = lambda_client.get_alias(FunctionName=function, Name=event['alias'])
                    alias_exists = True
                except lambda_client.exceptions.ResourceNotFoundException:
                    alias_exists = False
                if alias_exists:
                    action = 'update'
                    response = lambda_client.update_alias(**params)
                else:
                    action = 'create'
                    response = lambda_client.create_alias(**params)
                if response['ResponseMetadata']['HTTPStatusCode'] >= 400:
                    return {'statusCode': 500, 'body': f'Failed to {action} Lambda function alias'}
                else:
                    print('{}d alias "{}" to invoke version {}'.format(
                        action, response['Name'], response['FunctionVersion'])
                    )

        return {'statusCode': 200, 'body': 'Success'}
