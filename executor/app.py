import json
import uuid
import boto3
import datetime
from robot import run
from robot.api import ExecutionResult
import shutil
import os
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import logging
from allure_robotframework import allure_robotframework

logger = logging.getLogger(__name__)

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
    dynamodb = boto3.resource('dynamodb')
    testsbucket_name = os.environ['TestsBucketName']
    resultsbucket_name = os.environ['ResultsBucketName']
    testruntable_name = os.environ['TestRunTableName']
    testshardtable_name = os.environ['TestShardTableName']
    # generate filename like 2020-01-01T00:00:00.000Z.txt with current timestamp
    current_timestamp = datetime.datetime.utcnow().isoformat()
    test_run_table = dynamodb.Table(testruntable_name)
    test_shard_table = dynamodb.Table(testshardtable_name)
    for record in event['Records']:
        print("test")
        payload = json.loads(record["body"])
        run_id = payload.get("run_id", None)
        job_id = payload.get("job_id", None)
        project = payload.get('project', None)
        tests = payload.get('tests', None)
        shard_name = payload.get('shard_name', None)
        shard_content = payload.get('shard_content', None)
        download_s3_folder(testsbucket_name, project, '/tmp/' + project)
        print(str(payload))
        set_test_job_status(test_run_table, run_id, job_id, "IN_PROGRESS")
        options_dict = {'outputdir': f'/tmp/{project}/results/{run_id}',  'report': None, 'log': None, 'output':f'{job_id}.xml', 'listener':allure_robotframework(f'/tmp/{project}/results/{run_id}/allure-results')}
        if shard_content[0]["datadriver"]:
            dynamictest_list = "|".join([test["suite"] + "." + test["test"] for test in shard_content])
            dynamictest_arg = "DYNAMICTESTS:" + dynamictest_list
            # filename without extension
            
            run(f'/tmp/{project}/{tests}', **options_dict,  variable=[dynamictest_arg], suite=[shard_content[0]["suite"]])
        # if datadriver is False in the first test, run the test without datadriver
        else:
            # Create list of strings in test_list with format test["suite"].test["test"]
            test_list = ["*"+test["suite"] + "." + test["test"] for test in shard_content]
            run(f'/tmp/{project}/{tests}', **options_dict, test=test_list, suite=[shard_content[0]["suite"]])
        #s3.Bucket(resultsbucket_name).upload_file(f'/tmp/{project}/results/{run_id}/{job_id}.xml', f'{project}/results/{run_id}/{job_id}.xml')
        upload_folder_to_s3(resultsbucket_name, f'{project}/results/{run_id}', f'/tmp/{project}/results/{run_id}')
    # Delete tmp folder
    shutil.rmtree('/tmp', ignore_errors=True)
    set_test_job_status(test_run_table, run_id, job_id, "EXECUTED")

        # if run is not executed, return 202
    if is_run_executed(test_run_table, run_id):
        # Execute the merger lambda function
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(FunctionName=os.environ['MergerFunctionName'], InvocationType='Event', Payload=json.dumps({"run_id": run_id, "project": project}))

    return {
        "statusCode": 200
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


def set_test_job_status(table, run_id, job_id, job_status):
    try:
        response = table.update_item(
                Key={'run_id': run_id, 'job_id': job_id},
                UpdateExpression="set job_status=:s",
                ExpressionAttributeValues={
                    ':s': job_status},
                ReturnValues="UPDATED_NEW")
    except ClientError as err:
        logger.error(
            "Couldn't update test_run %s, test_job %s in table %s. Here's why: %s: %s",
            run_id, job_id, table.name,
            err.response['Error']['Code'], err.response['Error']['Message'])

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