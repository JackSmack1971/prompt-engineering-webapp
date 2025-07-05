#!/bin/bash

set -e

# Check if running in CI/CD environment
if [ -z "$CI" ]; then
    echo "Not running in CI/CD environment. Skipping ECR login and image push."
    # For local development, you might want to build the Docker image locally
    # docker build -t prompt-engineering-webapp:latest .
    exit 0
fi

# Set ECR registry (replace with actual registry)
AWS_ACCOUNT_ID="YOUR_AWS_ACCOUNT_ID"
AWS_REGION="us-east-1"
ECR_REPO_NAME="prompt-engineering-webapp"
ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build Docker image
docker build -t $ECR_REPO_NAME .

# Tag and push to ECR
docker tag $ECR_REPO_NAME:latest $ECR_REGISTRY/$ECR_REPO_NAME:latest
docker push $ECR_REGISTRY/$ECR_REPO_NAME:latest

echo "Docker image pushed to ECR: $ECR_REGISTRY/$ECR_REPO_NAME:latest"

# Deploy to ECS (example - replace with actual ECS deployment commands)
# aws ecs update-service --cluster YOUR_ECS_CLUSTER --service YOUR_ECS_SERVICE --force-new-deployment

echo "Deployment script finished."