# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from constructs import Construct
import aws_cdk as cdk
from huggingface_sagemaker.config import LATEST_PYTORCH_VERSION, LATEST_TRANSFORMERS_VERSION, region_dict

# policies based on https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html#sagemaker-roles-createmodel-perms
iam_sagemaker_actions = [
    "sagemaker:*",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetAuthorizationToken",
    "cloudwatch:PutMetricData",
    "cloudwatch:GetMetricData",
    "cloudwatch:GetMetricStatistics",
    "cloudwatch:ListMetrics",
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:DescribeLogStreams",
    "logs:PutLogEvents",
    "logs:GetLogEvents",
    "s3:CreateBucket",
    "s3:ListBucket",
    "s3:GetBucketLocation",
    "s3:GetObject",
    "s3:PutObject",
]


def get_image_uri(
    region=None,
    transformmers_version=LATEST_TRANSFORMERS_VERSION,
    pytorch_version=LATEST_PYTORCH_VERSION
):
    repository = f"{region_dict[region]}.dkr.ecr.{region}.amazonaws.com/huggingface-pytorch-inference"
    tag = f"{pytorch_version}-transformers{transformmers_version}-cpu-py36-ubuntu18.04"
    return f"{repository}:{tag}"


class HuggingfaceSagemaker(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Hugging Face Model
        huggingface_model = cdk.CfnParameter(
            self,
            "model",
            type="String",
            default=None,
        ).value_as_string
        # Model Task
        huggingface_task = cdk.CfnParameter(
            self,
            "task",
            type="String",
            default=None,
        ).value_as_string

        short_huggingface_model = cdk.CfnParameter(
            self,
            "modelShortName",
            type="String",
            default=None,
        ).value_as_string

        # creates the image_uir based on the instance type and region
        image_uri = get_image_uri(region=self.region)

        # creates new iam role for sagemaker using `iam_sagemaker_actions` as permissions or uses provided arn
        execution_role = iam.Role(
            self, "hf_sagemaker_execution_role", assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com")
        )
        execution_role.add_to_policy(iam.PolicyStatement(resources=["*"], actions=iam_sagemaker_actions))
        
        # Grant the GetBatchImage permission to the execution role
        execution_role_arn = execution_role.role_arn

        # defines and creates container configuration for deployment
        container_environment = {"HF_MODEL_ID": huggingface_model, "HF_TASK": huggingface_task}
        container = sagemaker.CfnModel.ContainerDefinitionProperty(environment=container_environment, image=image_uri)

        # creates SageMaker Model Instance
        model_name = f'model-{short_huggingface_model}'
        model = sagemaker.CfnModel(
            self,
            "hf_model",
            execution_role_arn=execution_role_arn,
            primary_container=container,
            model_name=model_name,
        )


        # Creates SageMaker Endpoint configurations
        endpoint_configuration_name = f'config-{short_huggingface_model}'
        endpoint_configuration = sagemaker.CfnEndpointConfig(
            self,
            "hf_serverless_endpoint_config",
            endpoint_config_name=endpoint_configuration_name,
            production_variants=[
                
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    model_name=model.model_name,
                    initial_variant_weight=1.0,
                    variant_name=model.model_name,
                    serverless_config=sagemaker.CfnEndpointConfig.ServerlessConfigProperty(
                        max_concurrency=3,
                        memory_size_in_mb=3072
                    ),
                )
            ],
        )
        # Creates Serverless Endpoint
        endpoint_name = f'serverless-endpoint-{short_huggingface_model}'
        endpoint = sagemaker.CfnEndpoint(
            self,
            "hf_serverless_endpoint",
            endpoint_name=endpoint_name,
            endpoint_config_name=endpoint_configuration.endpoint_config_name,
        )

        # adds depends on for different resources
        endpoint_configuration.node.add_dependency(model)
        endpoint.node.add_dependency(endpoint_configuration)
        model.node.add_dependency(execution_role)

