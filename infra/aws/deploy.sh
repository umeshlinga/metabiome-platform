#!/bin/bash
# =============================================================================
# MetaBiome Platform — AWS Deployment Script
# Deploys API (ECS Fargate) + Pipeline (AWS Batch) + Database (RDS) + S3
# Usage: ./deploy.sh --env production
# =============================================================================

set -euo pipefail

# ── Colors for output ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'

log()  { echo -e "${BLUE}[metabiome]${NC} $1"; }
ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Parse arguments ───────────────────────────────────────────────────────────
ENV="production"
REGION="us-east-1"
SKIP_INFRA=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)      ENV="$2";    shift 2 ;;
    --region)   REGION="$2"; shift 2 ;;
    --skip-infra) SKIP_INFRA=true; shift ;;
    --skip-build) SKIP_BUILD=true; shift ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT="metabiome"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
API_IMAGE="${ECR_REGISTRY}/${PROJECT}-api:latest"
FRONTEND_IMAGE="${ECR_REGISTRY}/${PROJECT}-frontend:latest"
CLUSTER="${PROJECT}-cluster"
API_SERVICE="${PROJECT}-api"
BATCH_QUEUE="${PROJECT}-pipeline-queue"
S3_RAW="${PROJECT}-raw-fastq-${ACCOUNT_ID}"
S3_RESULTS="${PROJECT}-pipeline-results-${ACCOUNT_ID}"
RDS_INSTANCE="${PROJECT}-db"

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  MetaBiome Platform — AWS Deploy${NC}"
echo -e "${BOLD}  Environment : ${GREEN}${ENV}${NC}"
echo -e "${BOLD}  Region      : ${REGION}${NC}"
echo -e "${BOLD}  Account     : ${ACCOUNT_ID}${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

# ── Step 1: Validate prerequisites ───────────────────────────────────────────
log "Step 1/7 — Checking prerequisites"

command -v aws    >/dev/null 2>&1 || fail "AWS CLI not installed. Run: brew install awscli"
command -v docker >/dev/null 2>&1 || fail "Docker not installed. Get it at docker.com"

aws sts get-caller-identity >/dev/null 2>&1 || fail "AWS credentials not configured. Run: aws configure"

ok "AWS CLI and Docker found"
ok "AWS credentials valid (account: ${ACCOUNT_ID})"

# ── Step 2: Create S3 buckets ─────────────────────────────────────────────────
log "Step 2/7 — Creating S3 buckets"

for BUCKET in "$S3_RAW" "$S3_RESULTS"; do
  if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
    ok "S3 bucket already exists: s3://${BUCKET}"
  else
    aws s3api create-bucket \
      --bucket "$BUCKET" \
      --region "$REGION" \
      $([ "$REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$REGION" || echo "")
    
    # Enable versioning for audit trail
    aws s3api put-bucket-versioning \
      --bucket "$BUCKET" \
      --versioning-configuration Status=Enabled
    
    # Block all public access
    aws s3api put-public-access-block \
      --bucket "$BUCKET" \
      --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    
    ok "Created S3 bucket: s3://${BUCKET}"
  fi
done

# ── Step 3: Create ECR repositories ──────────────────────────────────────────
log "Step 3/7 — Creating ECR repositories"

for REPO in "${PROJECT}-api" "${PROJECT}-frontend"; do
  if aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1; then
    ok "ECR repo already exists: ${REPO}"
  else
    aws ecr create-repository \
      --repository-name "$REPO" \
      --region "$REGION" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256
    ok "Created ECR repo: ${REPO}"
  fi
done

# ── Step 4: Build and push Docker images ──────────────────────────────────────
if [ "$SKIP_BUILD" = false ]; then
  log "Step 4/7 — Building and pushing Docker images"

  # Login to ECR
  aws ecr get-login-password --region "$REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
  ok "Logged in to ECR"

  # Build and push API image
  log "  Building API image..."
  docker build -f infra/docker/Dockerfile.api \
    -t "${PROJECT}-api:latest" \
    -t "$API_IMAGE" .
  docker push "$API_IMAGE"
  ok "API image pushed: ${API_IMAGE}"

  # Build and push frontend image
  log "  Building frontend image..."
  docker build -f infra/docker/Dockerfile.frontend \
    -t "${PROJECT}-frontend:latest" \
    -t "$FRONTEND_IMAGE" \
    ./frontend
  docker push "$FRONTEND_IMAGE"
  ok "Frontend image pushed: ${FRONTEND_IMAGE}"
else
  warn "Skipping Docker build (--skip-build)"
fi

# ── Step 5: Create ECS cluster ────────────────────────────────────────────────
log "Step 5/7 — Setting up ECS cluster"

if aws ecs describe-clusters --clusters "$CLUSTER" --region "$REGION" \
    --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
  ok "ECS cluster already exists: ${CLUSTER}"
else
  aws ecs create-cluster \
    --cluster-name "$CLUSTER" \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy \
      capacityProvider=FARGATE,weight=1 \
      capacityProvider=FARGATE_SPOT,weight=3 \
    --region "$REGION"
  ok "Created ECS cluster: ${CLUSTER}"
fi

# Register ECS task definition for API
log "  Registering ECS task definition"
aws ecs register-task-definition \
  --region "$REGION" \
  --cli-input-json "{
    \"family\": \"${PROJECT}-api\",
    \"networkMode\": \"awsvpc\",
    \"requiresCompatibilities\": [\"FARGATE\"],
    \"cpu\": \"512\",
    \"memory\": \"1024\",
    \"executionRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole\",
    \"containerDefinitions\": [
      {
        \"name\": \"${PROJECT}-api\",
        \"image\": \"${API_IMAGE}\",
        \"portMappings\": [{\"containerPort\": 8000, \"protocol\": \"tcp\"}],
        \"environment\": [
          {\"name\": \"ENVIRONMENT\", \"value\": \"${ENV}\"},
          {\"name\": \"AWS_REGION\",  \"value\": \"${REGION}\"},
          {\"name\": \"S3_BUCKET_RAW\",     \"value\": \"${S3_RAW}\"},
          {\"name\": \"S3_BUCKET_RESULTS\", \"value\": \"${S3_RESULTS}\"}
        ],
        \"logConfiguration\": {
          \"logDriver\": \"awslogs\",
          \"options\": {
            \"awslogs-group\": \"/ecs/${PROJECT}-api\",
            \"awslogs-region\": \"${REGION}\",
            \"awslogs-stream-prefix\": \"ecs\"
          }
        }
      }
    ]
  }" >/dev/null
ok "ECS task definition registered"

# ── Step 6: Set up AWS Batch for pipeline ─────────────────────────────────────
log "Step 6/7 — Setting up AWS Batch pipeline queue"

# Create compute environment
if ! aws batch describe-compute-environments \
    --compute-environments "${PROJECT}-compute" \
    --region "$REGION" \
    --query 'computeEnvironments[0].status' \
    --output text 2>/dev/null | grep -q "VALID"; then

  aws batch create-compute-environment \
    --compute-environment-name "${PROJECT}-compute" \
    --type MANAGED \
    --state ENABLED \
    --compute-resources "{
      \"type\": \"FARGATE_SPOT\",
      \"maxvCpus\": 256,
      \"subnets\": [],
      \"securityGroupIds\": []
    }" \
    --region "$REGION" >/dev/null
  ok "Created Batch compute environment"
else
  ok "Batch compute environment already exists"
fi

# Create job queue
if ! aws batch describe-job-queues \
    --job-queues "$BATCH_QUEUE" \
    --region "$REGION" \
    --query 'jobQueues[0].status' \
    --output text 2>/dev/null | grep -q "VALID"; then

  aws batch create-job-queue \
    --job-queue-name "$BATCH_QUEUE" \
    --state ENABLED \
    --priority 100 \
    --compute-environment-order \
      order=1,computeEnvironment="${PROJECT}-compute" \
    --region "$REGION" >/dev/null
  ok "Created Batch job queue: ${BATCH_QUEUE}"
else
  ok "Batch job queue already exists: ${BATCH_QUEUE}"
fi

# Register pipeline job definition
aws batch register-job-definition \
  --job-definition-name "${PROJECT}-pipeline-job" \
  --type container \
  --platform-capabilities FARGATE \
  --container-properties "{
    \"image\": \"${API_IMAGE}\",
    \"command\": [\"python\", \"-m\", \"pipeline.run\"],
    \"resourceRequirements\": [
      {\"type\": \"VCPU\",   \"value\": \"4\"},
      {\"type\": \"MEMORY\", \"value\": \"8192\"}
    ],
    \"jobRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/metabiome-batch-job-role\",
    \"networkConfiguration\": {\"assignPublicIp\": \"ENABLED\"},
    \"environment\": [
      {\"name\": \"S3_BUCKET_RAW\",     \"value\": \"${S3_RAW}\"},
      {\"name\": \"S3_BUCKET_RESULTS\", \"value\": \"${S3_RESULTS}\"},
      {\"name\": \"AWS_REGION\",        \"value\": \"${REGION}\"}
    ]
  }" \
  --region "$REGION" >/dev/null
ok "Batch job definition registered"

# ── Step 7: Deploy ECS service ────────────────────────────────────────────────
log "Step 7/7 — Deploying ECS service"

if aws ecs describe-services \
    --cluster "$CLUSTER" \
    --services "$API_SERVICE" \
    --region "$REGION" \
    --query 'services[0].status' \
    --output text 2>/dev/null | grep -q "ACTIVE"; then

  # Update existing service with new image
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$API_SERVICE" \
    --force-new-deployment \
    --region "$REGION" >/dev/null
  ok "ECS service updated — new deployment triggered"
else
  warn "ECS service not found — create it manually or via the AWS console"
  warn "Cluster: ${CLUSTER} | Service: ${API_SERVICE}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓ Deployment complete!${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}S3 buckets:${NC}"
echo -e "    Raw FASTQ  → s3://${S3_RAW}"
echo -e "    Results    → s3://${S3_RESULTS}"
echo ""
echo -e "  ${BOLD}ECS cluster:${NC}  ${CLUSTER} (${REGION})"
echo -e "  ${BOLD}Batch queue:${NC}  ${BATCH_QUEUE}"
echo -e "  ${BOLD}API image:${NC}    ${API_IMAGE}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "    1. Add GitHub Secrets (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)"
echo -e "    2. Push to main branch — CI/CD will auto-deploy"
echo -e "    3. Set POSTGRES_PASSWORD in AWS Secrets Manager"
echo ""
