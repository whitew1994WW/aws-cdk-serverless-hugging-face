#!/usr/bin/env python3
import aws_cdk as cdk
from config import ConfigManager
from huggingface_sagemaker.huggingface_sagemaker_endpoint_stack import HuggingfaceSagemakerServerlessEndpointStack
from huggingface_sagemaker.frontend_stack import FrontendStack


config = ConfigManager()
environment = cdk.Environment(account=config["AWS_ACCOUNT_INFO"]["AWS_ACCOUNT_ID"], region=config["AWS_ACCOUNT_INFO"]["AWS_REGION"])
app = cdk.App()
hugging_face_endpoint = HuggingfaceSagemakerServerlessEndpointStack(
    app,
    "HuggingfaceSagemaker",
    env=environment,
)
frontend_stack = FrontendStack(
    app,
    "FrontendStack",
    env=environment,
    api_gateway_id=hugging_face_endpoint.api_gateway_id
)
app.synth()
