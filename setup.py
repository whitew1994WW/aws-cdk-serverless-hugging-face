import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="sample_huggingface_sagemaker_cdk",
    version="0.0.1",

    description="An empty CDK Python app",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "sample_huggingface_sagemaker_cdk"},
    packages=setuptools.find_packages(where="sample_huggingface_sagemaker_cdk"),

    install_requires=[
        "aws-cdk.core==1.122.0",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
