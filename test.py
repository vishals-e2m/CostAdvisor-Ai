import boto3
import datetime
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
# Initialize OpenAI client (API key must be set in environment or config)
client = OpenAI(api_key="<your-openai-api-key>")  # Replace with your OpenAI API key

# Get AWS clients
ec2 = boto3.client('ec2')
rds = boto3.client('rds')
cloudwatch = boto3.client('cloudwatch')
ce = boto3.client('ce')
ebs = boto3.client('ec2')  # same as EC2 for volume access
s3 = boto3.client('s3')

# Set time range for the past 7 days
end = datetime.datetime.utcnow()
start = end - datetime.timedelta(minutes=5)
start_str = start.strftime('%Y-%m-%d')
end_str = end.strftime('%Y-%m-%d')

print(f"\n🔍 Scanning AWS resources from {start_str} to {end_str}...\n")

# Collect EC2 Instances with low utilization
def get_low_util_ec2():
    print("📦 Checking EC2 instances for low CPU usage...")
    instances = ec2.describe_instances()
    low_util = []

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
            datapoints = cw_metrics['Datapoints']
            avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints) if datapoints else 0
            if avg_cpu < 10:
                print(f"  ➤ EC2 {id} has average CPU: {avg_cpu:.2f}%")
                low_util.append((id, avg_cpu))
    return low_util

# Unattached EBS Volumes
def get_unattached_ebs():
    print("\n💽 Checking for unattached EBS volumes...")
    volumes = ebs.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
    ids = [vol['VolumeId'] for vol in volumes['Volumes']]
    for vid in ids:
        print(f"  ➤ Unattached EBS volume: {vid}")
    return ids

# RDS with low CPU
def get_low_util_rds():
    print("\n🛢️ Checking RDS instances for low CPU usage...")
    instances = rds.describe_db_instances()
    low_rds = []
    for inst in instances['DBInstances']:
        id = inst['DBInstanceIdentifier']
        print(f"\n🔎 Fetching metrics for RDS: {id}")
        metrics = cloudwatch.get_metric_statistics(
            Namespace='AWS/RDS',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': id}],
            StartTime=start,
            EndTime=end,
            Period=60,
            Statistics=['Average']
        )
        datapoints = sorted(metrics['Datapoints'], key=lambda x: x['Timestamp'])

        for dp in datapoints:
            print(f"   ⏱️ {dp['Timestamp']} - CPU: {dp['Average']:.2f}%")

        avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints) if datapoints else 0
        if avg_cpu < 10:
            print(f"  ⚠️ RDS {id} has LOW average CPU: {avg_cpu:.2f}%")
            low_rds.append((id, avg_cpu))
        else:
            print(f"  ✅ RDS {id} average CPU is OK: {avg_cpu:.2f}%")
    return low_rds

# S3 Misconfigurations
def get_s3_infrequent_access():
    print("\n🪣 Checking S3 buckets for storage class optimization...")
    s3_buckets = s3.list_buckets()['Buckets']
    misconfigured = []
    for bucket in s3_buckets:
        bucket_name = bucket['Name']
        try:
            s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        except Exception:
            print(f"  ➤ S3 bucket {bucket_name} may lack lifecycle/storage class rules.")
            misconfigured.append(bucket_name)
    return misconfigured

# MAIN RUNNER for LOCAL TEST
def main():
    print("🚀 Starting AWS Cost Optimization Analysis...\n")
    suggestions = []

    low_ec2 = get_low_util_ec2()
    for i in low_ec2:
        suggestions.append(f"EC2 {i[0]} has low CPU ({i[1]:.2f}%) – consider downsizing.")

    unattached = get_unattached_ebs()
    for vol in unattached:
        suggestions.append(f"EBS volume {vol} is unattached – consider deleting.")

    low_rds = get_low_util_rds()
    for rds_id, cpu in low_rds:
        suggestions.append(f"RDS {rds_id} low CPU ({cpu:.2f}%) – consider resizing.")

    s3_mis = get_s3_infrequent_access()
    for b in s3_mis:
        suggestions.append(f"S3 bucket {b} missing storage class optimization – consider Glacier or IA.")

    print("\n📊 Final Recommendations:\n")
    for suggestion in suggestions:
        print("✅", suggestion)

    if not suggestions:
        print("🎉 No major inefficiencies detected this week!")

    print("\n🧠 Generating summary with OpenAI...\n")
    try:
        prompt = (
            "Summarize the following AWS cost optimization findings in a professional tone, "
            "highlighting savings opportunities and possible actions:\n\n"
            + "\n".join(suggestions)
        )

        response = client.chat.completions.create(
            model="gpt-4",
         messages=[
        {
        "role": "system",
        "content": "You are an expert AWS cost advisor named Vishal. Sign your summaries with 'Kind Regards, Vishal, AWS Cost Advisor'."
        },
        {
        "role": "user",
        "content": prompt
        }
           ],

            temperature=0.5,
            max_tokens=300
        )

        summary = response.choices[0].message.content
        print("📄 Summary:\n")
        print(summary)

    except Exception as e:
        print("⚠️ Failed to generate OpenAI summary:", str(e))

# Run locally
if __name__ == '__main__':
    main()
