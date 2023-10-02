# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sagemaker as sagemaker
from constructs import Construct
import aws_cdk as cdk
from huggingface_sagemaker.config import LATEST_PYTORCH_VERSION, LATEST_TRANSFORMERS_VERSION, region_dict, LAMBDA_HANDLER_PATH
import pathlib


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


class HuggingfaceSagemakerServerlessEndpointStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Hugging Face Model
        huggingface_model, huggingface_task, short_huggingface_model = self.handle_inputs()

        # creates the image_uir based on the instance type and region
        image_uri = get_image_uri(region=self.region)

        execution_role = self.create_execution_role()

        model = self.create_model(image_uri, execution_role, huggingface_model, huggingface_task, short_huggingface_model)

        endpoint_configuration = self.create_endpoint_configuration(model, short_huggingface_model)
        endpoint = self.create_endpoint(endpoint_configuration, short_huggingface_model)

        lambda_role = self.create_lambda_role()
        code_path = pathlib.Path(__file__).parent / LAMBDA_HANDLER_PATH
        lambda_func = self.create_lambda_function(lambda_role, endpoint.endpoint_name, code_path)
        api_gateway = self.create_api_gateway(lambda_func, short_huggingface_model)

        self.record_outputs(model, endpoint_configuration, endpoint, lambda_func, execution_role, lambda_role, api_gateway)

        # adds depends on for different resources
        endpoint_configuration.node.add_dependency(model)
        endpoint.node.add_dependency(endpoint_configuration)
        model.node.add_dependency(execution_role)

    def handle_inputs(self):
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
        
        return huggingface_model,huggingface_task,short_huggingface_model

    def create_execution_role(self):
        # creates new iam role for sagemaker using `iam_sagemaker_actions` as permissions or uses provided arn
        execution_role = iam.Role(
            self, "hf_sagemaker_execution_role", assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com")
        )
        execution_role.add_to_policy(iam.PolicyStatement(resources=["*"], actions=iam_sagemaker_actions))
        return execution_role
    
    def create_model(self, image_uri, execution_role, huggingface_model, huggingface_task, short_huggingface_model):
                # defines and creates container configuration for deployment
        container_environment = {"HF_MODEL_ID": huggingface_model, "HF_TASK": huggingface_task}
        container = sagemaker.CfnModel.ContainerDefinitionProperty(environment=container_environment, image=image_uri)

        # creates SageMaker Model Instance
        model_name = f'model-{short_huggingface_model}'
        model = sagemaker.CfnModel(
            self,
            "hf_model",
            execution_role_arn=execution_role.role_arn,
            primary_container=container,
            model_name=model_name,
        )
        return model

    def create_endpoint_configuration(self, model, short_huggingface_model):
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
        return endpoint_configuration
    
    def create_endpoint(self, endpoint_configuration, short_huggingface_model):
        # Creates SageMaker Endpoint
        endpoint_name = f'serverless-endpoint-{short_huggingface_model}'
        endpoint = sagemaker.CfnEndpoint(
            self,
            "hf_serverless_endpoint",
            endpoint_name=endpoint_name,
            endpoint_config_name=endpoint_configuration.endpoint_config_name,
        )
        return endpoint
    
    def create_lambda_role(self):
        # Create a role for the lambda function
        lambda_role = iam.Role(
            self, "lambda_role", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        lambda_role.add_to_policy(iam.PolicyStatement(resources=["*"], actions=iam_sagemaker_actions))
        return lambda_role
    
    def create_lambda_function(self, lambda_role, endpoint_name, code_path):
        # Create a lambda function
        lambda_func = cdk.aws_lambda.Function(
            self,
            f"ApiLambda",
            runtime=cdk.aws_lambda.Runtime.PYTHON_3_8,
            handler="handler.lambda_handler",
            code=cdk.aws_lambda.Code.from_asset(str(code_path)),
            memory_size=1024,
            environment={
                "ENDPOINT_NAME": endpoint_name
            },
            role=lambda_role,
            timeout=cdk.Duration.seconds(180),
        )
        return lambda_func
    
    def create_api_gateway(self, lambda_func, short_huggingface_model):
        # Create log group
        log_group = cdk.aws_logs.LogGroup(self, f"api-gateway-logs")
        # Create API gateway
        api_gateway = cdk.aws_apigateway.LambdaRestApi(
            self,
            "ApiGatewayLambda",
            # This might give a type error but it is
            # Completely fine
            handler=lambda_func,
            rest_api_name=f"sagemaker-serverless-api",
            deploy_options=cdk.aws_apigateway.StageOptions(
                access_log_destination=cdk.aws_apigateway.LogGroupLogDestination(log_group),
                access_log_format=cdk.aws_apigateway.AccessLogFormat.json_with_standard_fields(
                    http_method=True,
                    ip=True,
                    caller=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            )
        )
        return api_gateway
    
    def record_outputs(self, model, endpoint_configuration, endpoint, lambda_function, execution_role, lambda_role, api_gateway):
        # Outputs
        cdk.CfnOutput(self, "model_name", value=model.model_name)
        cdk.CfnOutput(self, "endpoint_configuration_name", value=endpoint_configuration.endpoint_config_name)
        cdk.CfnOutput(self, "endpoint_name", value=endpoint.endpoint_name)
        cdk.CfnOutput(self, "execution_role_arn", value=execution_role.role_arn)
        cdk.CfnOutput(self, "lambda_function_name", value=lambda_function.function_name)
        cdk.CfnOutput(self, "lambda_function_arn", value=lambda_function.function_arn)
        cdk.CfnOutput(self, "lambda_role_arn", value=lambda_role.role_arn)
        cdk.CfnOutput(self, "api_gateway_url", value=api_gateway.url)
        # Register the rest api id
        cdk.CfnOutput(self, "api_gateway_id", value=api_gateway.rest_api_id)
        stack = cdk.Stack.of(self)
        stack.api_gateway_id = api_gateway.rest_api_id