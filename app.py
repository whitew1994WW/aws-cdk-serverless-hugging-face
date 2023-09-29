#!/usr/bin/env python3
import aws_cdk as cdk
from config import ConfigManager
from huggingface_sagemaker.huggingface_sagemaker import HuggingfaceSagemaker


config = ConfigManager()
app = cdk.App()
HuggingfaceSagemaker(
    app,
    "HuggingfaceSagemaker",
    env=cdk.Environment(account=config["AWS_ACCOUNT_INFO"]["AWS_ACCOUNT_ID"], region=config["AWS_ACCOUNT_INFO"]["AWS_REGION"]),
)

app.synth()
