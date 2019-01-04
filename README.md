# lambda-lambda-lambda
a Lambda function that can build and deploy other Lambda functions

![YO DAWG](meme.jpg)

AWS Lambda is a great tool for creating simple web services without the need to set up and maintain infrastructure.  However, once your code starts to require modules outside of the standard library, the task of packaging and deploying it can quickly devolve into a Rube Goldberg contraption.  For example, if your project requires Python's `cryptography` module, you cannot simply archive your virtualenv and upload it to Lambda unless, of course, your system is using the exact same version of OpenSSL that Lambda is.

You could go the route that many others have taken, procuring a Docker image based on the version of Amazon Linux that AWS Lambda is running on and packaging your code inside a container.  If you're pulling code from a private repository, you'll also need a secure means of automatically copying a deploy key or personal access token into the container.  Then you'll have to wait while the container launches, installs all the requirements, and uploads the resulting zip file to AWS.  When your deployment package starts to grow larger than a few megabytes, doing this repeatedly burns up a surprising amount of time.

You could also set up an EC2 instance running Amazon Linux and dedicate it to this purpose.  This is much faster but you'll have abstain from doing any system updates, lest you inadvertently break your deployment tool (for example, by upgrading `openssl`).  It's also costing the equivalent of a large, premium coffee every month unless you have the diligence to shut it down when you're not using it.

At this point, you may be struck by the irony of maintaining a bunch of convoluted plumbing in order to deploy serverless code, which was supposed to avoid that mess in the first place.  So why not build your project in its native environment from the start?  Well, because that comes with its own set of obstacles.  It's an immutable filesystem, so all your work will have to take place in `/tmp`.  That means your `$PATH` has to include `/tmp` first and in some cases you'll need to reference files by absolute paths.  `git` and `ssh` are also not available, nor is there a C compiler for building them.  Fortunately, there is a pure Python implementation of git called [Dulwich](https://dulwich.io/) that will handle the majority of git-related commands.  Sure, it's not as fast as a native binary, but we don't have that option in Lambda.  What we have now, though, is a two step procedure.  First, this Lambda function sets up a virtualenv containing Dulwich and its dependencies, archives that, and publishes it as a layer.  Once this is done, the function can be invoked again to build any other Python projects, as long as they include a `build.yaml` file that defines the files to include.  This function can separate dependencies and other common data into layers, so you don't need to deploy those parts if they haven't changed.  It also strips out things that are unnecessary or redundant in the Lambda runtime environment, such as vendored modules, tests, and documentation, keeping the size of the package to a minimum.  With this method, you have the speed of the EC2 solution above but only pay for the Lambda invocations and S3 storage, which cost next to nothing.

### Installation
1. Create an S3 bucket to store deployments, if you don't already have one.
1. Create a personal access token on GitHub.  See [this guide](https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/) for instructions.
1. Copy config.ini.example to config.ini and add your AWS account info.
1. Run `setup.py init`.  This script will do the following:
    * Create the Lambda function if it does not yet exist.
    * Package the latest boto3 (at the time of this writing, the version in AWS Lambda does not support layers).
    * Package an empty placeholder module for Dulwich and PyYAML.  This is to avoid `ModuleNotFoundError` when bootstrapping the function for the first time.
    * Publish these artifacts as a layer, and update the Lambda function with the new layer information.
    * Invoke the Lambda function, causing it to install Dulwich and PyYAML natively within the Lambda environment, republish that layer, and then update itself.
The Lambda function is now ready to build and deploy other Lambda functions.  If you need to update the lambda-lambda-lambda code, simply run `setup.py` again--it's idempotent.  The `init` parameter is only necessary to bootstrap the function with a newer boto3 and the placeholder modules.

### Usage
To build and deploy your own Lambda projects:
1. Copy the `deploy.sh` script from this repo to your project's directory.
1. Copy `build.yaml.example` to your project's directory and rename it to `build.yaml` (or if you prefer JSON, you can do the same with `build.json.example`).
1. Edit `build.yaml.example` and specify any files or folders to be included in your deployment.  At the very minimum, this file must contain a `function` section that defines the runtime(s) and the path to the file that contains the handler function.  You can separate common code or infrequently-updated files in the `layers` section for faster deployments.
1. Set the `AWS_PROFILE` and `AWS_REGION` environment variables or define them in `config.ini`.
1. Run `./deploy.sh` to build and deploy your project.  The following command line arguments are available and can alternatively be set in `config.ini`:
    * `-c CONFIG_FILE` (defaults to `config.ini`)
    * `-f FUNCTION_NAME` (defaults to the name of the project directory)
    * `-g GIT_REPO` (defaults to the name of the project directory)
    * `-l LOG_FILE` (defaults to `deploy.log`)
    * `-b GIT_BRANCH` (defaults to `master`)
    * `-p AWS_PROFILE`
    * `-r AWS_REGION`
    * `-t` track the build/deploy execution time
    * `-y` do not prompt before deploying

The first time you build and deploy using this tool it may be relatively slow due to cold starts.  Once the function is warm it can build and deploy a function in as little as 2 seconds.
