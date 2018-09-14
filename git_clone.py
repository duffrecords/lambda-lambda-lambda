#!/usr/bin/env python

""" Clones a repo from a URL.

pip won't be able to download from URLs since it requires git, which isn't
available in the AWS Lambda environment.  Instead, clone or pull it with Dulwich
and then install it as a local module.
"""

import os
import sys
from dulwich import porcelain

cwd = os.getcwd()
username = os.environ['git_username']
token = os.environ['git_token']
repo_urls = sys.argv[1:]
for repo_url in repo_urls:
    module_name = repo_url.split('/')[-1].split('@')[0]
    if username in repo_url:
        repo_url = repo_url.replace('://', f'://{token}:x-oauth-basic@')
    src_dir = f'{cwd}/venv/src/{module_name}'
    print(f"cloning {repo_url}...")
    try:
        porcelain.clone(repo_url, src_dir)
    except FileExistsError:
        porcelain.pull(src_dir, repo_url)
