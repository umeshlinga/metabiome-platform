# MetaBiome Platform — AWS Deployment Guide

## Prerequisites

1. AWS account — [aws.amazon.com/free](https://aws.amazon.com/free)
2. AWS CLI installed and configured (`aws configure`)
3. Docker Desktop running

---

## One-command deploy

```bash
cd infra/aws
chmod +x deploy.sh
./deploy.sh --env production --region us-east-1
```

The script will:
1. Create S3 buckets for FASTQ and results storage
2. Create ECR repositories for Docker images
3. Build and push API + frontend Docker images
4. Create ECS Fargate cluster
5. Set up AWS Batch compute environment and job queue
6. Deploy the API as an ECS service

---

## What gets created in AWS

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `metabiome-raw-fastq-{account_id}` | Stores uploaded FASTQ files |
| S3 bucket | `metabiome-pipeline-results-{account_id}` | Stores BAM, VCF, reports |
| ECR repo | `metabiome-api` | API Docker image |
| ECR repo | `metabiome-frontend` | Frontend Docker image |
| ECS cluster | `metabiome-cluster` | Runs API container |
| Batch queue | `metabiome-pipeline-queue` | Runs pipeline jobs |
| Batch compute | `metabiome-compute` | Fargate Spot instances for pipeline |

---

## GitHub Actions CI/CD setup

Add these 3 secrets to your GitHub repo:
`Settings → Secrets → New repository secret`

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_REGION` | `us-east-1` |

After adding secrets, every push to `main` will automatically:
1. Run Pytest pipeline tests
2. Run API tests
3. Build Docker images
4. Push to ECR
5. Deploy to ECS

---

## Manual steps after running deploy.sh

1. **Set database password in AWS Secrets Manager:**
```bash
aws secretsmanager create-secret \
  --name metabiome/postgres-password \
  --secret-string "your-strong-password-here"
```

2. **Create RDS PostgreSQL instance** (via AWS Console):
   - Engine: PostgreSQL 15
   - Instance: db.t3.micro (free tier)
   - Database name: metabiome
   - Enable: automated backups, encryption

3. **Run database migrations:**
```bash
docker compose exec api alembic upgrade head
```

4. **Upload reference genomes to S3:**
```bash
aws s3 cp GRCh38.fa s3://metabiome-references/GRCh38/genome.fa
```

---

## Estimated AWS costs (free tier)

| Service | Free tier | After free tier |
|---|---|---|
| ECS Fargate | 750 hrs/month | ~$0.04/vCPU/hr |
| AWS Batch | Pay per job | ~$0.04/vCPU/hr (Spot) |
| S3 | 5GB storage | $0.023/GB/month |
| RDS | 750 hrs db.t3.micro | ~$0.02/hr |
| ECR | 500MB storage | $0.10/GB/month |

For a dev/demo environment, monthly cost is typically **under $5**.
