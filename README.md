# rf-lambda-executor

Run Robot Framework Tests via AWS Lambda

Find more documentation about RF and AWS Lambda [here](https://manykarim.github.io/robotframework-and-lambda/).

It is parallel test execution project that splits up your test cases into multiple Lambda functions and executes them in parallel.

It uses multiple AWS Ressources:

- [AWS Lambda](https://aws.amazon.com/lambda/) to execute Robot Framework tests and use its API
- [AWS S3](https://aws.amazon.com/s3/) to store the test cases and the test results
- [AWS DynamoDB](https://aws.amazon.com/dynamodb/) to store the run status
- [AWS SQS](https://aws.amazon.com/sqs/) to communicate between the Lambda functions
- [AWS CloudFormation](https://aws.amazon.com/cloudformation/) to create the AWS Ressources

You can find the sample project [here](https://github.com/manykarim/rf-lambda-executor) and you can clone it with the command below:  

```bash
git clone https://github.com/manykarim/rf-lambda-executor
```

It will be featured at [RoboCon 2023](https://robocon.io/) in the my talk [To Infinity and Beyond - Serverless scaling with AWS Lambda](https://robocon.io/#to-infinity-and-beyond---serverless-scaling-with-aws-lambda).

## Project Structure

```bash	
.
├── distributor
│   ├── app.py
│   ├── __init__.py
│   ├── Listener
│   │   ├── DistributorListener.py
│   │   └── __init__.py
│   └── requirements.txt
├── executor
│   ├── app.py
│   ├── Dockerfile
│   ├── __init__.py
│   └── requirements.txt
├── LICENSE
├── merger
│   ├── app.py
│   ├── __init__.py
│   └── requirements.txt
├── poetry.lock
├── pyproject.toml
├── README.md
├── samconfig.toml
└── template.yaml
```

The most important parts are:

- the `distributor` , `executor` and `merger` folders which contain the Lambda functions
- the `template.yaml` file which contains the CloudFormation stack

### template.yaml

The `template.yaml` file is the main file for the CloudFormation stack. It contains all the AWS Ressources that will be created and the Lambda functions that will be deployed.  
It is a YAML file using the [SAM Specification](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-specification.html).

### Lambda Functions

The Lambda functions are located in the `distributor` , `executor` and `merger` folders.

#### Distributor
The distributor is the first Lambda function that will be executed.  
It is responsible for splitting up the test cases into smaller chunks and sending them to the executor Lambda function.  
It is triggered by an HTTP Post request to the API Gateway.  

It will 

- download the test cases from the S3 Bucket `Testsbucket`
- split up the tests into N small chunks of similar size
- create a DynamoDB entry for each chunk
- send each chunk to a SQS queue to the executor Lambda function

The dependencies are defined in the `distributor/requirements.txt` file.

#### Executor
Is the second Lambda function that will be executed.
It is responsible for executing the test cases and sending the results to the merger Lambda function.
It is triggered by a message in the SQS queue.

It will

- download the test cases from the S3 Bucket `Testsbucket`
- execute the test cases
- upload the results to the S3 Bucket `Resultsbucket`
- send the results to the merger Lambda function
- update the DynamoDB entry
- check if all chunks are finished and trigger the merger Lambda function

Due to the size of the dependencies (e.g. `robotframework-browser`) the executor Lambda function is deployed as a Docker container.  
The Dockerfile is located in the `executor` folder.

#### Merger
Is the third Lambda function that will be executed.
It is responsible for merging the results from the executor Lambda functions and sending the results to the S3 Bucket `Resultsbucket`.
It is triggered either by the executor Lambda function or by a HTTP Get request to the API Gateway.

It will

- download the results from the S3 Bucket `Resultsbucket`
- merge the results using `rebot`
- upload the results to the S3 Bucket `Resultsbucket` in the folder `final`
- update the DynamoDB entry

The dependencies are defined in the `merger/requirements.txt` file.