# Jenkins Pipeline Guide

The `Jenkinsfile` is a single-service pipeline for this Python backend. It builds the root `Dockerfile`, pushes one image to Amazon ECR, and updates an existing Amazon ECS service.

## Pipeline flow

```text
Load Config -> Checkout -> Test -> SonarQube (optional) -> Build and Push
                                                          -> Production approval (production only)
                                                          -> Deploy (dev, qa, uat, or production)
```

## Jenkins requirements

The Jenkins agent must have:

- Git
- Python 3.11 or later
- Docker with permission to access the Docker daemon
- AWS CLI
- `sonar-scanner` when SonarQube is enabled

Jenkins must also have these plugins and credentials:

- Config File Provider plugin
- Pipeline plugin
- `aws-credentials` as an AWS credential
- `sonarqube-token` as a Secret Text credential when SonarQube is enabled

## Managed config file

Set the `CONFIG_FILE_ID` build parameter to a Jenkins Config File Provider entry containing these values:

```properties
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com
ECR_REPOSITORY=crowd-backend
AWS_REGION=us-east-1
ECS_CLUSTER=crowdvision
ECS_SERVICE=crowd-backend
ECS_TASK_DEFINITION=crowd-backend
ECS_EXECUTION_ROLE_ARN=arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole
ECS_TASK_ROLE_ARN=arn:aws:iam::ACCOUNT:role/crowd-backend-task-role
ECS_LOG_GROUP=/ecs/crowd-backend
SECRETS_BUNDLE_ARN=arn:aws:secretsmanager:REGION:ACCOUNT:secret:NAME
DEPLOY_ENVIRONMENT=dev
```

`SONAR_HOST_URL` is optional. When it is present, the pipeline runs `sonar-scanner` using the Jenkins `sonarqube-token` credential. Set `DEPLOY_ENVIRONMENT` to `none` to run checks and build the image without deploying. Production values (`production` or `prod`) pause for manual approval.

## Deployment behavior

The pipeline expects the ECR repository and ECS service to already exist. It does not create AWS infrastructure. Before deployment it renders the placeholders in `ecs-task-definition.json`, registers a new ECS task-definition revision, updates the service, and waits for ECS to stabilize.

The versioned image tag is `${BUILD_NUMBER}-${short commit SHA}`. The same tag is used for the ECS deployment; `latest` is also pushed for convenience.
