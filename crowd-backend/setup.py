from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="crowdvision",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Production-grade crowd counting and analysis system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "crowdvision-train=scripts.train:main",
            "crowdvision-evaluate=scripts.evaluate:main",
            "crowdvision-api=api.main:start_server",
        ],
    },
)
