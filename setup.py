"""
用户中心SDK的安装配置文件
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="user-center-sdk",
    version="1.1.0",
    author="User Center Team",
    author_email="admin@usercenter.com",
    description="用户中心API的统一SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/usercenter/user-center-sdk",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "pyjwt>=2.0.0",
    ],
    extras_require={
        "django": ["django>=2.2.0"],
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.10.0",
            "black>=20.8b1",
            "isort>=5.7.0",
            "flake8>=3.8.4",
            "mypy>=0.800",
        ],
    },
)
