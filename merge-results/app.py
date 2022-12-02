import json
import uuid
import boto3
import datetime
from robot import rebot, rebot_cli
from robot.api import ExecutionResult

import os


def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """


    s3 = boto3.resource('s3')
    resultsbucket_name = os.environ['ResultsBucketName']
    # generate filename like 2020-01-01T00:00:00.000Z.txt with current timestamp
    current_timestamp = datetime.datetime.utcnow().isoformat()
 
    # Get event['project'], default to None
    project = event.get('project', None)
    # Get event['tests'], default to None
    tests = event.get('tests', None)
    # Get event['run_id'], default to None
    run_id = event.get('run_id', None)
   
    if project and run_id:
        print('Downloading results folder from s3 bucket to tmp')
        print(f"project: {project} testsuite: {run_id}")
        # Download project folder from s3 bucket to tmp
        download_s3_folder(resultsbucket_name, f'{project}/results/{run_id}', f'/tmp/{project}/results/{run_id}')
        # Print all files and folders recursively
        print_all_files_and_folders_recursively(f'/tmp/{project}/results/')
        #rebot(f'/tmp/{project}/results/{run_id}/*.xml', outputdir=f'/tmp/{project}/results/{run_id}/final', output=f'output.xml', log=f'log.html', report=f'report.html')
        rebot_cli([f"--outputdir=/tmp/{project}/results/{run_id}/final", "--output=output.xml", "--log=log.html", "--report=report.html", "--merge", "--nostatusrc", f"/tmp/{project}/results/{run_id}/*.xml"], exit=False)
        result = ExecutionResult(f'/tmp/{project}/results/{run_id}/final/output.xml')
        tests_passed = result.suite.statistics.passed
        tests_failed = result.suite.statistics.failed
        tests_total = result.suite.statistics.total
        # Upload .xml file to s3 bucket
        
        s3.Bucket(resultsbucket_name).upload_file(f'/tmp/{project}/results/{run_id}/final/output.xml', f'{project}/results/{run_id}/final/output.xml')

    return {
        "statusCode": 200,
        "body": json.dumps({
            "run_id": run_id,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "tests_total": tests_total,
        }),
    }

def download_s3_folder(bucket_name, s3_folder, local_dir=None):
    """
    Download the contents of a folder directory
    Args:
        bucket_name: the name of the s3 bucket
        s3_folder: the folder path in the s3 bucket
        local_dir: a relative or absolute directory path in the local file system
    """
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name)
    for obj in bucket.objects.filter(Prefix=s3_folder):
        target = obj.key if local_dir is None \
            else os.path.join(local_dir, os.path.relpath(obj.key, s3_folder))
        if not os.path.exists(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        if obj.key[-1] == '/':
            continue
        bucket.download_file(obj.key, target)

def print_all_files_and_folders_recursively(path):
    for root, dirs, files in os.walk(path):
        level = root.replace(path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print('{}{}'.format(subindent, f))