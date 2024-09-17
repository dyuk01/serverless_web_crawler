from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_lambda_python_alpha as _alambda,
    aws_dynamodb as _dynamodb,
    aws_sqs as _sqs,
    aws_lambda_event_sources as _event_source
)
from constructs import Construct

class ServerlessWebCrawlerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Dynamo Model
        # PK: VisitedURL
        # SK: RunId#Date
        # SourceURL (Where Did I come from?)
        # RootURL (Where Did I start?)

        #Dynamo - CrawledURLs Table
        table = _dynamodb.Table(self, "CrawledURLs",
            table_name="CrawledURLs",
            partition_key=_dynamodb.Attribute(name="crawledURL", type=_dynamodb.AttributeType.STRING),
            sort_key=_dynamodb.Attribute(name="runId", type=_dynamodb.AttributeType.STRING),
            billing_mode=_dynamodb.BillingMode.PAY_PER_REQUEST
        )

        #SQS - PendingCrawls
        crawlerQueue = _sqs.Queue(self, "WebCrawlerQueue", queue_name="WebCrawlerQueue")
        crawlerDLQ = _sqs.Queue(self, "WebCrawler-DLQ", queue_name="WebCrawler-DLQ")

        #Initiator
        initiatorFunction = _alambda.PythonFunction(
            self,
            "InitiatorFn",
            entry="./lambda/",
            runtime=_lambda.Runtime.PYTHON_3_12,
            index="initiator.py",
            handler="handle"
        )

        #Crawler
        crawlerFunction = _alambda.PythonFunction(
            self,
            "CrawlerFn",
            entry="./lambda/",
            runtime=_lambda.Runtime.PYTHON_3_12,
            index="crawler.py",
            handler="handle",

            # Prevents too many requests at once. (Number of requests at once)
            reserved_concurrent_executions=2,
            dead_letter_queue_enabled=True,
            dead_letter_queue=crawlerDLQ
        )
        

        #Queue read write permissions
        crawlerQueue.grant_send_messages(initiatorFunction)
        crawlerQueue.grant_send_messages(crawlerFunction)
        crawlerQueue.grant_consume_messages(crawlerFunction)

        #DynamoDB read write permissions
        table.grant_read_write_data(initiatorFunction)
        table.grant_read_write_data(crawlerFunction)

        #Subscribe Crawler to SQS
        event_source = _event_source.SqsEventSource(crawlerQueue, batch_size=1)
        
        crawlerFunction.add_event_source(event_source)



        