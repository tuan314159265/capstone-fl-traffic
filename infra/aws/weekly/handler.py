"""Small scheduler trigger: only the fixed SSM training document can be sent."""
from datetime import datetime, timezone
import json
import os
import boto3


def handler(event, context):
    if datetime.now(timezone.utc) >= datetime.fromisoformat(os.environ['END_DATE'].replace('Z', '+00:00')):
        return {'status': 'skipped', 'reason': 'collection_deadline_reached'}
    instance = os.environ['INSTANCE_ID']
    reservations = boto3.client('ec2').describe_instances(InstanceIds=[instance])['Reservations']
    state = reservations[0]['Instances'][0]['State']['Name']
    if state != 'running':
        print(json.dumps({'status': 'skipped', 'reason': 'instance_' + state}))
        return {'status': 'skipped', 'reason': 'instance_' + state}
    command = boto3.client('ssm').send_command(
        InstanceIds=[instance], DocumentName=os.environ['SSM_DOCUMENT'],
        DocumentVersion='$DEFAULT', TimeoutSeconds=300,
        Comment='Weekly bounded TomTom FedAvg training',
    )['Command']
    result = {'status': 'submitted', 'command_id': command['CommandId'], 'instance_id': instance}
    print(json.dumps(result))
    return result
