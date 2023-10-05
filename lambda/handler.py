import os
import io
import boto3
import json


# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
runtime= boto3.client('runtime.sagemaker')

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    
    data = json.loads(json.dumps(event))
    text_inupt = data['body'].split('=')[1]
    model_input = {"inputs": [{
        "label": "Input",
        "content": text_inupt,
        "type": "text"}]
    }
    print(text_inupt)
    
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME,
                                       ContentType='application/json',
                                       Body=json.dumps(model_input))
    print(response)
    result = json.loads(response['Body'].read().decode())
    print(result)
    
    return {
        'statusCode' : 200,
        'headers': {
            'Content-Type': 'text/plain'
        },
        'body' : json.dumps(result)
    } 