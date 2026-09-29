#!/usr/bin/env bash
set -euo pipefail

script_path=${1:?Usage: ssm-send.sh SCRIPT [COMMENT]}
comment=${2:-Meridian deployment operation}
: "${EC2_INSTANCE_ID:?Set the EC2_INSTANCE_ID repository variable}"
: "${AWS_REGION:?Set AWS_REGION}"
: "${APP_DIR:?Set APP_DIR}"

command_file=$(mktemp)
trap 'rm -f "$command_file"' EXIT

jq -n \
  --arg app_dir "$APP_DIR" \
  --arg aws_region "$AWS_REGION" \
  --arg backend_image "${BACKEND_IMAGE:-}" \
  --arg frontend_image "${FRONTEND_IMAGE:-}" \
  --arg secret_name "${APP_SECRET_NAME:-Meridian-Secret-For-EC2}" \
  --rawfile body "$script_path" \
  '{commands: [("APP_DIR=" + ($app_dir | @sh) + " AWS_REGION=" + ($aws_region | @sh) + " BACKEND_IMAGE=" + ($backend_image | @sh) + " FRONTEND_IMAGE=" + ($frontend_image | @sh) + " SECRET_NAME=" + ($secret_name | @sh) + " bash -s <<\u0027MERIDIAN_SSM_SCRIPT\u0027\n" + $body + "\nMERIDIAN_SSM_SCRIPT\n")]}' \
  > "$command_file"

command_id=$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$EC2_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "$comment" \
  --parameters "file://$command_file" \
  --query 'Command.CommandId' \
  --output text)

echo "SSM command: $command_id"
for attempt in $(seq 1 60); do
  status=$(aws ssm get-command-invocation \
    --region "$AWS_REGION" \
    --command-id "$command_id" \
    --instance-id "$EC2_INSTANCE_ID" \
    --query Status \
    --output text 2>/dev/null || true)

  case "$status" in
    Success)
      aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$command_id" --instance-id "$EC2_INSTANCE_ID" --query StandardOutputContent --output text
      exit 0
      ;;
    Failed|Cancelled|TimedOut|Cancelling)
      aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$command_id" --instance-id "$EC2_INSTANCE_ID" --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' --output json || true
      exit 1
      ;;
    *)
      echo "[$attempt/60] SSM status: ${status:-Pending}"
      sleep 10
      ;;
  esac
done

aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$command_id" --instance-id "$EC2_INSTANCE_ID" --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' --output json || true
exit 1
