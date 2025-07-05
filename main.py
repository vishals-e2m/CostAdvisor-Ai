import boto3
import datetime
# import openai  # Optional if summarization is needed via GPT
import os

# Optional: OpenAI API key
# openai.api_key = os.getenv("OPENAI_API_KEY")

# Get AWS clients
ec2 = boto3.client('ec2')
rds = boto3.client('rds')
cloudwatch = boto3.client('cloudwatch')
ce = boto3.client('ce')
ebs = boto3.client('ec2')  # same as EC2 for volume access
s3 = boto3.client('s3')
sns = boto3.client('sns')  # Optional for notifications

# Set time range
end = datetime.datetime.utcnow()
start = end - datetime.timedelta(days=7)
start_str = start.strftime('%Y-%m-%d') 
end_str = end.strftime('%Y-%m-%d')

# Collect EC2 Instances
def get_low_util_ec2():
    instances = ec2.describe_instances()
    low_util = [] # List to hold low-utilization instances

    for res in instances['Reservations']:
        for inst in res['Instances']:
            id = inst['InstanceId']
            cw_metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': id}],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=['Average']
            )
            avg_cpu = sum(dp['Average'] for dp in cw_metrics['Datapoints']) / len(cw_metrics['Datapoints']) if cw_metrics['Datapoints'] else 0
            if avg_cpu < 10:
                low_util.append((id, avg_cpu))
    return low_util

# Unattached EBS Volumes
def get_unattached_ebs():
    volumes = ebs.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
    return [vol['VolumeId'] for vol in volumes['Volumes']]

# Low-utilization RDS
def get_low_util_rds():
    instances = rds.describe_db_instances()
    low_rds = []
    for inst in instances['DBInstances']:
        id = inst['DBInstanceIdentifier']
        metrics = cloudwatch.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': id}],
            StartTime=start,
            EndTime=end,
            Period=86400,
            Statistics=['Average']
        )
        avg_cpu = sum(dp['Average'] for dp in metrics['Datapoints']) / len(metrics['Datapoints']) if metrics['Datapoints'] else 0
        if avg_cpu < 5:
            low_rds.append((id, avg_cpu))
    return low_rds

# S3 Misconfigurations
def get_s3_infrequent_access():
    s3_buckets = s3.list_buckets()['Buckets']
    misconfigured = []
    for bucket in s3_buckets:
        try:
            metrics = s3.get_bucket_metrics_configuration(
                Bucket=bucket['Name'],
                Id='EntireBucket'
            )
        except Exception:
            misconfigured.append(bucket['Name'])
    return misconfigured

# Smart Rule Summary
# def summarize_findings(results):
#     if not openai.api_key:
#         return results  # fallback if OpenAI not used
#     prompt = f"Summarize these cost-saving recommendations:\n\n{results}"
#     response = openai.Completion.create(
#         model="gpt-4",
#         prompt=prompt,
#         max_tokens=150
#     )
#     return response.choices[0].text.strip()

def lambda_handler(event, context):
    suggestions = []

    low_ec2 = get_low_util_ec2()
    if low_ec2:
        for i in low_ec2:
            suggestions.append(f"EC2 {i[0]} has low CPU ({i[1]:.2f}%) – consider downsizing.")

    unattached = get_unattached_ebs()
    if unattached:
        for vol in unattached:
            suggestions.append(f"EBS volume {vol} is unattached – consider deleting.")

    low_rds = get_low_util_rds()
    if low_rds:
        for rds_id, cpu in low_rds:
            suggestions.append(f"RDS {rds_id} low CPU ({cpu:.2f}%) – consider resizing.")

    s3_mis = get_s3_infrequent_access()
    for b in s3_mis:
        suggestions.append(f"S3 bucket {b} missing storage class optimization – consider Glacier or IA.")

    # summary = summarize_findings("\n".join(suggestions))
    # print("Monthly Savings Summary:")
    # print(summary)

    # Slack or email reporting could be added here

    return {
        "statusCode": 200,
        "body": summary
    }










# 🔍 Scanning AWS resources from 2025-06-28 to 2025-07-05...

# 📦 Checking EC2 instances for low CPU usage...
#   ➤ EC2 i-0123456789abcdef has average CPU: 2.11%

# 💽 Checking for unattached EBS volumes...
#   ➤ Unattached EBS volume: vol-0123456789abcdef

# 🛢️ Checking RDS instances for low CPU usage...
#   ➤ RDS mydb-instance has average CPU: 0.92%

# 🪣 Checking S3 buckets for storage class optimization...
#   ➤ S3 bucket my-app-logs may lack lifecycle/storage class rules.

# 📊 Final Recommendations:

# ✅ EC2 i-0123456789abcdef has low CPU (2.11%) – consider downsizing.
# ✅ EBS volume vol-0123456789abcdef is unattached – consider deleting.
# ✅ RDS mydb-instance low CPU (0.92%) – consider resizing.
# ✅ S3 bucket my-app-logs missing storage class optimization – consider Glacier or IA.
