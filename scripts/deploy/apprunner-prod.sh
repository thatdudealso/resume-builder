#!/usr/bin/env bash
# Provision / update ResumeBild on AWS App Runner.
# Never prints secret values. Requires AWS CLI credentials with admin access.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REPO="${ECR_REPO:-resumebild-backend}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
SERVICE_NAME="${SERVICE_NAME:-resumebild}"
SECRET_ID="${SECRET_ID:-resumebild/production/app}"
DOMAIN="${DOMAIN:-resumebild.5432wire.com}"
VPC_ID="${VPC_ID:-vpc-048753329152aac59}"
PRIVATE_SUBNET_1="${PRIVATE_SUBNET_1:-subnet-004529816cc0138a7}"
PRIVATE_SUBNET_2="${PRIVATE_SUBNET_2:-subnet-08d004f7a6f596506}"
RDS_SG_ID="${RDS_SG_ID:-sg-0ec898004f55b218a}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
ACCESS_ROLE_ARN="${ACCESS_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID}:role/resumebild-apprunner-ecr-access}"
INSTANCE_ROLE_ARN="${INSTANCE_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID}:role/resumebild-apprunner-instance}"

echo "==> Ensuring ECR repository ${ECR_REPO}"
aws ecr describe-repositories --repository-names "${ECR_REPO}" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "${ECR_REPO}" --image-scanning-configuration scanOnPush=true >/dev/null

echo "==> Logging in to ECR"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" >/dev/null

echo "==> Building and pushing image ${ECR_URI}:${IMAGE_TAG} (linux/amd64)"
docker build --platform linux/amd64 -t "${ECR_REPO}:${IMAGE_TAG}" .
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:latest"
docker push "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:latest"

echo "==> Ensuring Secrets Manager secret ${SECRET_ID} exists"
if ! aws secretsmanager describe-secret --secret-id "${SECRET_ID}" >/dev/null 2>&1; then
  echo "Secret ${SECRET_ID} is missing." >&2
  exit 1
fi

CONNECTOR_NAME="${CONNECTOR_NAME:-resumebild-vpc}"
CONNECTOR_ARN="$(aws apprunner list-vpc-connectors --query "VpcConnectors[?VpcConnectorName=='${CONNECTOR_NAME}'].VpcConnectorArn | [0]" --output text)"
if [[ -z "${CONNECTOR_ARN}" || "${CONNECTOR_ARN}" == "None" ]]; then
  echo "==> Creating security group + VPC connector for private RDS access"
  EXISTING_SG="$(aws ec2 describe-security-groups --filters Name=group-name,Values=resumebild-apprunner Name=vpc-id,Values=${VPC_ID} --query 'SecurityGroups[0].GroupId' --output text)"
  if [[ -z "${EXISTING_SG}" || "${EXISTING_SG}" == "None" ]]; then
    APPRUNNER_SG_ID="$(aws ec2 create-security-group \
      --group-name resumebild-apprunner \
      --description "ResumeBild App Runner egress" \
      --vpc-id "${VPC_ID}" \
      --query GroupId --output text)"
  else
    APPRUNNER_SG_ID="${EXISTING_SG}"
  fi
  aws ec2 authorize-security-group-ingress \
    --group-id "${RDS_SG_ID}" \
    --protocol tcp --port 5432 \
    --source-group "${APPRUNNER_SG_ID}" >/dev/null 2>&1 || true
  CONNECTOR_ARN="$(aws apprunner create-vpc-connector \
    --vpc-connector-name "${CONNECTOR_NAME}" \
    --subnets "${PRIVATE_SUBNET_1}" "${PRIVATE_SUBNET_2}" \
    --security-groups "${APPRUNNER_SG_ID}" \
    --query VpcConnector.VpcConnectorArn --output text)"
fi

SERVICE_ARN="$(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"
RUNTIME_ENV_SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "${SECRET_ID}" --query ARN --output text)"

SOURCE_CONFIG=$(cat <<EOF
{
  "AuthenticationConfiguration": {
    "AccessRoleArn": "${ACCESS_ROLE_ARN}"
  },
  "ImageRepository": {
    "ImageIdentifier": "${ECR_URI}:${IMAGE_TAG}",
    "ImageRepositoryType": "ECR",
    "ImageConfiguration": {
      "Port": "8000",
      "RuntimeEnvironmentSecrets": {
        "DATABASE_URL": "${RUNTIME_ENV_SECRET_ARN}:DATABASE_URL::",
        "JWT_SECRET": "${RUNTIME_ENV_SECRET_ARN}:JWT_SECRET::",
        "OPENAI_API_KEY": "${RUNTIME_ENV_SECRET_ARN}:OPENAI_API_KEY::",
        "COGNITO_USER_POOL_ID": "${RUNTIME_ENV_SECRET_ARN}:COGNITO_USER_POOL_ID::",
        "COGNITO_APP_CLIENT_ID": "${RUNTIME_ENV_SECRET_ARN}:COGNITO_APP_CLIENT_ID::",
        "S3_BUCKET": "${RUNTIME_ENV_SECRET_ARN}:S3_BUCKET::"
      },
      "RuntimeEnvironmentVariables": {
        "ENV": "production",
        "DEPLOY_ENV": "production",
        "COGNITO_REGION": "us-east-1",
        "PUBLIC_BASE_URL": "https://${DOMAIN}",
        "AUTH_LOGIN_URL": "https://5432wire.com/login",
        "AUTH_RETURN_ALLOWLIST": "https://${DOMAIN}",
        "CORS_ORIGINS": "https://${DOMAIN}",
        "S3_PREFIX": "resumebild",
        "S3_REGION": "${AWS_REGION}",
        "APP_VERSION": "${IMAGE_TAG}",
        "PAYMENTS_ENABLED": "false",
        "REDIS_URL": "redis://127.0.0.1:9/0"
      }
    }
  },
  "AutoDeploymentsEnabled": false
}
EOF
)

INSTANCE_CONFIG=$(cat <<EOF
{
  "Cpu": "0.25 vCPU",
  "Memory": "0.5 GB",
  "InstanceRoleArn": "${INSTANCE_ROLE_ARN}"
}
EOF
)

if [[ -z "${SERVICE_ARN}" || "${SERVICE_ARN}" == "None" ]]; then
  echo "==> Creating App Runner service ${SERVICE_NAME}"
  SERVICE_ARN="$(aws apprunner create-service \
    --service-name "${SERVICE_NAME}" \
    --source-configuration "${SOURCE_CONFIG}" \
    --instance-configuration "${INSTANCE_CONFIG}" \
    --network-configuration "EgressConfiguration={EgressType=VPC,VpcConnectorArn=${CONNECTOR_ARN}}" \
    --health-check-configuration 'Protocol=HTTP,Path=/ready,Interval=10,Timeout=5,HealthyThreshold=1,UnhealthyThreshold=5' \
    --query Service.ServiceArn --output text)"
else
  echo "==> Updating App Runner service ${SERVICE_NAME}"
  aws apprunner update-service \
    --service-arn "${SERVICE_ARN}" \
    --source-configuration "${SOURCE_CONFIG}" \
    --instance-configuration "${INSTANCE_CONFIG}" \
    --network-configuration "EgressConfiguration={EgressType=VPC,VpcConnectorArn=${CONNECTOR_ARN}}" >/dev/null
fi

echo "==> Waiting for service running"
for i in $(seq 1 60); do
  STATUS="$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --query Service.Status --output text)"
  echo "status=${STATUS}"
  if [[ "${STATUS}" == "RUNNING" ]]; then
    break
  fi
  if [[ "${STATUS}" == "CREATE_FAILED" || "${STATUS}" == "UPDATE_FAILED" || "${STATUS}" == "DELETED" ]]; then
    echo "Service entered ${STATUS}" >&2
    exit 1
  fi
  sleep 15
done

SERVICE_URL="$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --query Service.ServiceUrl --output text)"
echo "App Runner default URL: https://${SERVICE_URL}"

echo "==> Associating custom domain ${DOMAIN}"
aws apprunner associate-custom-domain \
  --service-arn "${SERVICE_ARN}" \
  --domain-name "${DOMAIN}" \
  --no-enable-www-subdomain >/dev/null 2>&1 || true

DOMAIN_INFO="$(aws apprunner describe-custom-domains --service-arn "${SERVICE_ARN}" --output json)"
echo "${DOMAIN_INFO}" | python3 - <<'PY'
import json,sys
info=json.load(sys.stdin)
domains=info.get("CustomDomains") or []
if not domains:
    print("No custom domain association found yet")
    raise SystemExit(0)
d=domains[0]
print(f"custom_domain_status={d.get('Status')}")
for rec in d.get("CertificateValidationRecords") or []:
    print(f"validation_cname={rec.get('Name')}->{rec.get('Value')}")
PY

# Upsert Route53 alias to the App Runner domain target when certificate validation records exist.
HOSTED_ZONE_ID="${HOSTED_ZONE_ID:-Z04820823MQE3EMJX7VND}"
APP_RUNNER_DNS="$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --query Service.ServiceUrl --output text)"
# App Runner custom domains use alias to the service URL hostname.
python3 - <<PY
import json,subprocess,os
hosted=os.environ.get("HOSTED_ZONE_ID","${HOSTED_ZONE_ID}")
domain="${DOMAIN}"
target="${APP_RUNNER_DNS}"
# Prefer App Runner regional dualstack target if provided via cert records DNSTarget
info=json.loads(subprocess.check_output([
  "aws","apprunner","describe-custom-domains","--service-arn","${SERVICE_ARN}","--output","json"
], text=True))
dns_target = None
for d in info.get("CustomDomains") or []:
    dns_target = d.get("DNSTarget") or dns_target
if dns_target:
    target = dns_target
change={
  "Comment": f"ResumeBild App Runner alias for {domain}",
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": domain,
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "Z01915732ZBZKC8SH57SF",
        "DNSName": target if target.endswith(".") else target+".",
        "EvaluateTargetHealth": True
      }
    }
  }]
}
# App Runner hosted zone IDs vary by region; discover from validation if needed.
open("/tmp/resumebild-route53.json","w").write(json.dumps(change))
print(f"route53_upsert={domain}->{target}")
PY
aws route53 change-resource-record-sets --hosted-zone-id "${HOSTED_ZONE_ID}" --change-batch file:///tmp/resumebild-route53.json >/dev/null
rm -f /tmp/resumebild-route53.json

echo "Done. Verify: curl -fsS https://${DOMAIN}/health"
