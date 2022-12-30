import json
from robot import run
import uuid
import boto3
import datetime
# import the DistributorListener class which is located in the Subfolder Listener/ in a file called DistributorListener.py
from Listener.DistributorListener import DistributorListener
import os
import shutil


def lambda_handler(event, context):
    s3 = boto3.resource('s3')
    dynamodb = boto3.resource('dynamodb')
    sqs = boto3.client('sqs')
    # Get queue url from environment variable
    testjob_queue_url = os.environ['TestJobQueueName']
    testsbucket_name = os.environ['TestsBucketName']
    resultsbucket_name = os.environ['ResultsBucketName']
    testruntable_name = os.environ['TestRunTableName']
    testshardtable_name = os.environ['TestShardTableName']
    # generate filename like 2020-01-01T00:00:00.000Z.txt with current timestamp
    current_timestamp = datetime.datetime.utcnow().isoformat()
    test_run_table = dynamodb.Table(testruntable_name)
    test_shard_table = dynamodb.Table(testshardtable_name)
    if event["body"]:
        data=json.loads(event["body"])
    else:
        data=event
    # Get event['project'], default to None
    project = data.get('project', None)
    # Get event['tests'], default to tests/
    tests = data.get('tests', 'tests/')
    # Get event['run_id'], default to None
    run_id = data.get('run_id', str(uuid.uuid4()))
    # Get event['shards'], default to None
    shards = int(data.get('shards', 1))
    # if project and testsuite are not None, then download project folder from s3 bucket to tmp
    if project and tests:
        print('Downloading project folder from s3 bucket to tmp')
        print(f"project: {project} testsuite: {tests}")
        # Download project folder from s3 bucket to tmp
        download_s3_folder(testsbucket_name, project, '/tmp/' + project)
        # Create a dry run with no report, log, or output
        dry_run = run(f'/tmp/{project}/{tests}', dryrun=True, listener=DistributorListener(shards, f'/tmp/{project}/distributor_output/'), output=None, log=None, report=None, runemptysuite=True, quiet=True)
        for file in os.listdir(f'/tmp/{project}/distributor_output/'):
            if file.endswith(".json"):
                # read the json file
                filename = file.split(".")[0]
                with open(f'/tmp/{project}/distributor_output/{file}') as f:
                    shard_data = json.load(f)
                    job_id = str(uuid.uuid4())
                    response = test_run_table.put_item(
                                Item={'run_id': run_id, 'job_status': 'NOT STARTED', 'job_id': job_id, 'shards': shards})
                    response = test_shard_table.put_item(
                            Item={'run_id': run_id, 'shard_name': filename, 'shard_content': shard_data, 'job_id': job_id})
                    message_body = json.dumps({'project': project, 'run_id': run_id, 'shard_name': filename, 'shard_content': shard_data, 'job_id': job_id, 'tests': tests})
                    # Send message to sqs queue
                    response = sqs.send_message(
                        QueueUrl=testjob_queue_url,
                        MessageBody=message_body,
                        MessageAttributes={
                            'project': {
                                'DataType': 'String',
                                'StringValue': project
                            },
                            'run_id': {
                                'DataType': 'String',
                                'StringValue': run_id
                            },
                            'job_id': {
                                'DataType': 'String',
                                'StringValue': job_id
                            }
                        }
                    )
        # Delete tmp folder
        shutil.rmtree('/tmp', ignore_errors=True)
        return {
            'statusCode': 200,
            'body': json.dumps(f'Test run {run_id} created')
        }
    else:
        return {
            'statusCode': 400,
            'body': json.dumps('project and testsuite are required')
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

