import json
import uuid
import boto3
import os
import sys
import shutil
import datetime
from robot import rebot, rebot_cli
from robot.api import ExecutionResult
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import logging

logger = logging.getLogger(__name__)
import os


def lambda_handler(event, context):
    
    http_method = event.get('httpMethod')
    query_string = event.get('queryStringParameters')
    headers = event.get('headers')
    body = event.get('body')
    if query_string is not None:
        # Get event['project'], default to None
        project = query_string.get('project', None)
        # Get event['run_id'], default to None
        run_id = query_string.get('run_id', None)
    else:
        # Get event['project'], default to None
        project = event.get('project', None)
        # Get event['run_id'], default to None
        run_id = event.get('run_id', None)
    s3 = boto3.resource('s3')
    dynamodb = boto3.resource('dynamodb')
    resultsbucket_name = os.environ['ResultsBucketName']
    testruntable_name = os.environ['TestRunTableName']
    test_run_table = dynamodb.Table(testruntable_name)
    # generate filename like 2020-01-01T00:00:00.000Z.txt with current timestamp
    current_timestamp = datetime.datetime.utcnow().isoformat()

    if is_run_merged(test_run_table, run_id):
        print('Downloading results folder from s3 bucket to tmp')
        print(f"project: {project} testsuite: {run_id}")
        # Download project folder from s3 bucket to tmp
        download_s3_folder(resultsbucket_name, f'{project}/results/{run_id}/final', f'/tmp/{project}/results/{run_id}/final')
        result = ExecutionResult(f'/tmp/{project}/results/{run_id}/final/output.xml')
        set_test_run_status(test_run_table, run_id, "MERGED")
        tests_passed = result.suite.statistics.passed
        tests_failed = result.suite.statistics.failed
        tests_total = result.suite.statistics.total
        return {
            "statusCode": 200,
            "body": json.dumps({
                "run_id": run_id,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "tests_total": tests_total,
                "download_xml": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/output.xml",
                "download_log": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/log.html",
                "download_report": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/report.html",
                "allure_results": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/allure-results"
            })
        }
    

    # if run is not executed, return 202
    if not is_run_executed(test_run_table, run_id):
        return {
            'statusCode': 202,
            'body': json.dumps('Run is not fully executed')
        }
   
    if project and run_id:
        print('Downloading results folder from s3 bucket to tmp')
        print(f"project: {project} testsuite: {run_id}")
        # Download project folder from s3 bucket to tmp
        download_s3_folder(resultsbucket_name, f'{project}/results/{run_id}', f'/tmp/{project}/results/{run_id}')
        rebot_cli([f"--outputdir=/tmp/{project}/results/{run_id}/final", "--output=output.xml", "--log=log.html", "--report=report.html", "--merge", "--nostatusrc", f"/tmp/{project}/results/{run_id}/*.xml"], exit=False)
        result = ExecutionResult(f'/tmp/{project}/results/{run_id}/final/output.xml')
        set_test_run_status(test_run_table, run_id, "MERGED")
        tests_passed = result.suite.statistics.passed
        tests_failed = result.suite.statistics.failed
        tests_total = result.suite.statistics.total
        # Upload .xml file to s3 bucket
        #s3.Bucket(resultsbucket_name).upload_file(f'/tmp/{project}/results/{run_id}/final/output.xml', f'{project}/results/{run_id}/final/output.xml')
        upload_folder_to_s3(resultsbucket_name, f'{project}/results/{run_id}/final', f'/tmp/{project}/results/{run_id}/final')
    # Delete tmp folder
    shutil.rmtree('/tmp', ignore_errors=True)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "run_id": run_id,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "tests_total": tests_total,
            "download_xml": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/output.xml",
            "download_log": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/log.html",
            "download_report": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/final/report.html",
            "allure_results": f"s3://{resultsbucket_name}.s3.amazonaws.com/{project}/results/{run_id}/allure-results"

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
        if not target.startswith(f"{s3_folder}/allure-results/"):
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

def upload_folder_to_s3(bucket_name, s3_folder, local_dir):
    """
    Upload the contents of a folder directory
    Args:
        bucket_name: the name of the s3 bucket
        s3_folder: the folder path in the s3 bucket
        local_dir: a relative or absolute directory path in the local file system
    """
    client = boto3.client('s3')

    # enumerate local files recursively
    for root, dirs, files in os.walk(local_dir):

        for filename in files:

            # construct the full local path
            local_path = os.path.join(root, filename)

            # construct the full Dropbox path
            relative_path = os.path.relpath(local_path, local_dir)
            s3_path = os.path.join(s3_folder, relative_path)

            # relative_path = os.path.relpath(os.path.join(root, filename))

            print(f'Searching {s3_path} in {bucket_name}')
            try:
                client.head_object(Bucket=bucket_name, Key=s3_path)
                print(f"Path found on S3! Skipping {s3_path}")

                # try:
                    # client.delete_object(Bucket=bucket, Key=s3_path)
                # except:
                    # print "Unable to delete %s..." % s3_path
            except:
                print("Uploading {s3_path}...")
                client.upload_file(local_path, bucket_name, s3_path)


def is_run_executed(table, run_id):
    try:
        response = table.query(KeyConditionExpression=Key('run_id').eq(run_id))
    except ClientError as err:
        logger.error(
            "Couldn't query for test_runs with run_id in %s. Here's why: %s: %s", run_id,
            err.response['Error']['Code'], err.response['Error']['Message'])
        raise
    else:
        # If all items in response['Items'] have item['job_status'] == COMPLETED, return True
        # Otherwise, return False
        return all(item['job_status'] == 'EXECUTED' for item in response['Items'])

def is_run_merged(table, run_id):
    try:
        response = table.query(KeyConditionExpression=Key('run_id').eq(run_id))
    except ClientError as err:
        logger.error(
            "Couldn't query for test_runs with run_id in %s. Here's why: %s: %s", run_id,
            err.response['Error']['Code'], err.response['Error']['Message'])
        raise
    else:
        # If all items in response['Items'] have item['job_status'] == MERGED, return True
        # Otherwise, return False
        return all(item['job_status'] == 'MERGED' for item in response['Items'])


def set_test_run_status(table, run_id, run_status):
    try:
        test_jobs = table.query(KeyConditionExpression=Key('run_id').eq(run_id))
        for item in test_jobs['Items']:
            response = table.update_item(
                Key={'run_id': run_id, 'job_id': item['job_id']},
                UpdateExpression="set job_status=:s",
                ExpressionAttributeValues={
                    ':s': run_status},
                ReturnValues="UPDATED_NEW")
    except ClientError as err:
        logger.error(
            "Couldn't update test_run %s, in table %s. Here's why: %s: %s",
            run_id, table.name,
            err.response['Error']['Code'], err.response['Error']['Message'])