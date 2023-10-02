from constructs import Construct
import aws_cdk as cdk
from huggingface_sagemaker.config import LATEST_PYTORCH_VERSION, LATEST_TRANSFORMERS_VERSION, region_dict, LAMBDA_HANDLER_PATH
import pathlib as path


class FrontendStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, api_gateway_id, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        inputs = self.handle_inputs()
       # Create S3 bucket
        website_bucket = cdk.aws_s3.Bucket(
            self,
            "S3Bucket",
            block_public_access=cdk.aws_s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        origin_access_identity = cdk.aws_cloudfront.OriginAccessIdentity(
            self,
            "OriginAccessIdentity",
            comment="Origin access identity for HuggingFace",
        )

        website_bucket.grant_read(origin_access_identity)

        deployment = cdk.aws_s3_deployment.BucketDeployment(self, "DeployWebsite",
            sources=[cdk.aws_s3_deployment.Source.asset('frontend_code')],
            destination_bucket=website_bucket,
        )

        # CloudFront Security & Headers
        security_headers_beahaviour = cdk.aws_cloudfront.ResponseSecurityHeadersBehavior(
            content_type_options=cdk.aws_cloudfront.ResponseHeadersContentTypeOptions(
                override=True,
            ),
            frame_options=cdk.aws_cloudfront.ResponseHeadersFrameOptions(
                frame_option=cdk.aws_cloudfront.HeadersFrameOption.DENY, override=True
            ),
            strict_transport_security=cdk.aws_cloudfront.ResponseHeadersStrictTransportSecurity(
                access_control_max_age=cdk.Duration.seconds(31536000),
                preload=True,
                include_subdomains=True,
                override=True,
            ),
            xss_protection=cdk.aws_cloudfront.ResponseHeadersXSSProtection(
                protection=True,
                mode_block=True,
                override=True,
            ),
            referrer_policy=cdk.aws_cloudfront.ResponseHeadersReferrerPolicy(
                referrer_policy=cdk.aws_cloudfront.HeadersReferrerPolicy.SAME_ORIGIN,
                override=True,
            ),
        )

        cloudfront_response_headers_policy = cdk.aws_cloudfront.ResponseHeadersPolicy(
            self,
            "CloudFrontResponseHeadersPolicy",
            comment="Security response headers for HuggingFace",
            custom_headers_behavior=cdk.aws_cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cdk.aws_cloudfront.ResponseCustomHeader(
                        header="server", value="ModelZoo", override=True
                    )
                ]
            ),
            security_headers_behavior=security_headers_beahaviour,
        )

        # Create CloudFront Distribution
        cloudfront_cache_policy = cdk.aws_cloudfront.CachePolicy(
            self,
            "CloudFrontCachePolicy",
            cache_policy_name="hugging-face-cache-policy",
            comment="Cache policy for hugging face",
            default_ttl=cdk.Duration.minutes(30),
            min_ttl=cdk.Duration.minutes(1),
            max_ttl=cdk.Duration.days(10),
            enable_accept_encoding_brotli=True,
            enable_accept_encoding_gzip=True,
        )

        
        api_origin = cdk.aws_cloudfront_origins.HttpOrigin(
            f"{api_gateway_id}.execute-api.{self.region}.{cdk.Aws.URL_SUFFIX}",
            origin_path='/prod',
            protocol_policy=cdk.aws_cloudfront.OriginProtocolPolicy.HTTPS_ONLY
        )

        cloudfront_distribution: cdk.aws_cloudfront.Distribution = cdk.aws_cloudfront.Distribution(
            self,
            "CloudFrontDistribution",
            comment="CloudFront Distribution for hugging face",
            default_behavior=cdk.aws_cloudfront.BehaviorOptions(
                allowed_methods=cdk.aws_cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cdk.aws_cloudfront.CachedMethods.CACHE_GET_HEAD,
                cache_policy=cloudfront_cache_policy,
                response_headers_policy=cloudfront_response_headers_policy,
                viewer_protocol_policy=cdk.aws_cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                origin=cdk.aws_cloudfront_origins.S3Origin(
                    bucket=website_bucket, origin_access_identity=origin_access_identity
                ),
            ),
            additional_behaviors={
                "api/*": cdk.aws_cloudfront.BehaviorOptions(
                    origin=api_origin,
                    allowed_methods=cdk.aws_cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cdk.aws_cloudfront.CachePolicy.CACHING_DISABLED,
                    viewer_protocol_policy=cdk.aws_cloudfront.ViewerProtocolPolicy.HTTPS_ONLY
                )
            },
            default_root_object="index.html",
            error_responses=[
                cdk.aws_cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=cdk.Duration.seconds(0),
                )
            ],
        )
        

        print("Manually change the distribution in the console to support HTTP3")

        cdk.CfnOutput(
            self,
            "S3BucketName",
            export_name="HuggingFace:FrontendBucketName",
            value=website_bucket.bucket_name,
        )

        cdk.CfnOutput(
            self,
            "S3BucketArn",
            export_name="HuggingFace:FrontendBucketArn",
            value=website_bucket.bucket_arn,
        )

        cdk.CfnOutput(
            self,
            "S3BucketUrl",
            export_name="HuggingFace:FrontendBucketURL",
            value=website_bucket.s3_url_for_object(),
        )

        cdk.CfnOutput(
            self,
            "CloudFrontDistributionId",
            export_name="HuggingFace:FrontendDistributionId",
            value=cloudfront_distribution.distribution_id,
        )
        
        cdk.CfnOutput(
            self,
            "CloudFrontDomainName",
            export_name="shoppinglist:FrontendDomainName",
            value=cloudfront_distribution.domain_name,
        )

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