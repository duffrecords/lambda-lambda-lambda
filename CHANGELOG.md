# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- N/A

## [1.0.0] - 2019-01-03
### Added
- Support for Lambda layers, allowing dependencies and other common data to be deployed independently of main function code.

### Changed
- GitHub personal access tokens are now optional and will be ignored if the repo is public.
- deploy.sh is now parameterized for more flexibility

### Breaking Changes
- [Installation](https://github.com/duffrecords/lambda-lambda-lambda/tree/v1.0.0#installation) and [usage](https://github.com/duffrecords/lambda-lambda-lambda/tree/v1.0.0#usage) have completely changed, to support the new Lambda layers functionality.  This release is not backwards compatible with previous releases.  Please read those sections of the [README](https://github.com/duffrecords/lambda-lambda-lambda/blob/v1.0.0/README.md) for more details.

### Bug Fixes
- Fixed a bug that deleted dependencies if they had not been updated since the last run.

### Removed
- CloudFormation template has been removed since setup.py accomplishes the same thing.

## [0.1.0] - 2018-12-13
### Added
- Support for branches other than master.
- CloudFormation template for initial setup.
