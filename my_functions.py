#----------------
# my_functions.py
#-----------------
import boto3
import datetime 
import os
from botocore.exceptions import ClientError
import time
import logging

def logging_setup(logfile):
  logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', filename=logfile, level=logging.DEBUG)
  logger = logging.getLogger(__name__)
  return logger

def log(Service, Name):
  print(f'{datetime.datetime.now(tz=datetime.timezone.utc)}\t{Service}\t{Name}')

def setup_vpc(vpc_name='myvpc', vpc_cidr='10.0.0.0/16'):
  ec2 = boto3.resource('ec2')
  client = boto3.client('ec2')
  response = client.describe_vpcs(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ vpc_name ]
      }
    ]
  )
  if response['Vpcs']:
    vpc = ec2.Vpc(response['Vpcs'][0]['VpcId'])
    log('VPC already exists', vpc_name)
  else:
    vpc = ec2.create_vpc(
      CidrBlock=vpc_cidr,
      TagSpecifications=[
        {
          'ResourceType': 'vpc',
          'Tags':[
            {
              "Key": "Name",
              "Value": vpc_name
            },
          ]
        }
      ]
    )
    log('VPC created', vpc_name)
  return vpc

def setup_internet_gateways(igw_name, vpc):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  response = client.describe_internet_gateways(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ igw_name ]
      }
    ]
  )
  if response['InternetGateways']:
    internet_gateway = ec2.InternetGateway(response['InternetGateways'][0]['InternetGatewayId'])
    log('Internet Gateway already exits', igw_name)
  else:
    internet_gateway = ec2.create_internet_gateway(
      TagSpecifications=[
        {
          'ResourceType': 'internet-gateway',
          'Tags':[
            {
              "Key": "Name",
              "Value": igw_name
            },
          ]
        }
      ]
    )
    vpc.attach_internet_gateway(InternetGatewayId=internet_gateway.id)
    log('Internet Gateway created', igw_name)
  return internet_gateway

def setup_route_table(route_table_name, vpc, GatewayId):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  response = client.describe_route_tables(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ route_table_name ]
      }
    ]
  )
  if response['RouteTables']:
    route_table = ec2.RouteTable(response['RouteTables'][0]['RouteTableId'])
    log('Route Table already exists', route_table_name)
  else:
    route_table = vpc.create_route_table(
      TagSpecifications=[
        {
          'ResourceType': 'route-table',
          'Tags':[
            {
              "Key": "Name",
              "Value": route_table_name
            },
          ]
        }
      ]
    )
    route = route_table.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=GatewayId)
    log('Route Table created', route_table_name)
  return route_table

def setup_instance(AMI, subnet_id, security_group_id, instance_name, key_pair_name, userdata, instance_type, bool_public):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  response = client.describe_instances(
    Filters=[
      {
        'Name' : 'tag:Name',
        'Values' : [ instance_name ]
      },
      {
        'Name' : 'instance-state-name',
        'Values' : [ 'running', 'pending']
      }
    ]
  )
  if response['Reservations']:
    instance = ec2.Instance(response['Reservations'][0]['Instances'][0]['InstanceId'])
    log('EC2 Instance already exists', instance_name)
  else:
    instances = ec2.create_instances(
      BlockDeviceMappings=[
#        {
#            'DeviceName': '/dev/sdh',
#            'VirtualName': 'ephemeral0',
#            "NoDevice": ''
#        },
#        {
#            'DeviceName': '/dev/sdi',
#            'VirtualName': 'ephemeral1',
#            "NoDevice": ""
#        },
        {
            'DeviceName': '/dev/sdb',
            'Ebs': {
                'DeleteOnTermination': False,
                'VolumeSize': 30,
                'VolumeType': 'gp3',
                'Encrypted': True
            },
        },
        ],
      ImageId=AMI,
      InstanceType=instance_type,
      EbsOptimized=True,
      MaxCount=1,
      MinCount=1,
      NetworkInterfaces=[
        {
          'SubnetId': subnet_id,
          'DeviceIndex': 0,
          'AssociatePublicIpAddress': bool_public,
          'Groups': [security_group_id],
          }
      ],
      KeyName=key_pair_name,
      UserData=userdata,
      TagSpecifications=[
        {
          'ResourceType': 'instance',
          'Tags':[
            {
              "Key": "Name",
              "Value": instance_name
            },
            {
              "Key": "auto-delete",
              "Value": "no"
            }
          ]
        }
      ]
    )
    instance = instances[0]
#    waiter = client.get_waiter('instance_status_ok')
#    waiter.wait(
#      InstanceIds=[instance.id]
#    )
    log('EC2 Instance created', instance_name)
  return instance
 
def setup_subnet(subnet_name, subnet_cidr, AZ, vpc, route_table):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')

  # check if subnet already exists.
  response = client.describe_subnets(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ subnet_name ]
      }
    ]
  )
  if response['Subnets']:
    subnet = ec2.Subnet(response['Subnets'][0]['SubnetId'])
    log('Subnet already exists', subnet_name)
  else:
    subnet = ec2.create_subnet(
      CidrBlock=subnet_cidr, 
      VpcId=vpc.id,
      AvailabilityZone=AZ,
      TagSpecifications=[
        {
          'ResourceType': 'subnet',
          'Tags':[
            {
              "Key": "Name",
              "Value": subnet_name
            },
          ]
        }
      ]
    )
  route_table.associate_with_subnet(SubnetId=subnet.id)
  log('Subnet', subnet_name)
  return subnet

def setup_security_group(sg_name, vpc_id):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')

  response = client.describe_security_groups(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ sg_name ]
      }
    ]
  )
  if response['SecurityGroups']:
    security_group = ec2.SecurityGroup(response['SecurityGroups'][0]['GroupId'])
  else:
    security_group = ec2.create_security_group(
      GroupName=sg_name, 
      Description='----', 
      VpcId=vpc_id,
      TagSpecifications=[
        {
          'ResourceType': 'security-group',
          'Tags':[
            {
              "Key": "Name",
              "Value": sg_name
            },
          ]
        }
      ] 
    )      
    security_group.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=22, ToPort=22)
    security_group.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=80, ToPort=80)
  log('Security Group', sg_name)
  return security_group

def is_key_pair_exists(key_pair_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  # create a file to store the key locally
  response = client.describe_key_pairs(
    Filters=[
      {
        'Name' : "key-name",
        "Values" : [ key_pair_name ]
      }
    ]
  )
  if response(['KeyPairs']) == 0:
    return False
  else:
    return True

def create_key_pair(key_pair_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  key_pair_file = key_pair_name + ".pem"
  if os.path.exists(key_pair_file):
    os.remove(key_pair_file)
  outfile = open(key_pair_file, 'w')
  # create a key pair
  key_pair = ec2.create_key_pair(
    KeyName=key_pair_name,
    TagSpecifications=[
      {
        'ResourceType': 'key-pair',
        'Tags':[
          {
            "Key": "Name",
            "Value": key_pair_name
          },
        ]
      }
    ] 
  )
  # capture the key and store it in a file
  outfile.write(str(key_pair.key_material))
  log('Key pair', key_pair_name)
  return True
  
def setup_key_pair(key_pair_name):
  if not is_key_pair_exists(key_pair_name):
    create_key_pair(key_pair_name)

def setup_eip(eip_name):
  client = boto3.client('ec2')
  response = client.describe_addresses(
      Filters=[
          {
              'Name': 'tag:Name',
              'Values': [eip_name] 
          },
      ]
  )
  if response['Addresses']:
    AllocationId = response['Addresses'][0]['AllocationId']
  else:
    eip = client.allocate_address(
      Domain='vpc',
      TagSpecifications=[
        {
          'ResourceType': 'elastic-ip',
          'Tags':[
            {
              "Key": "Name",
              "Value": eip_name
            },
          ]
        }
      ]
    )
    AllocationId = eip['AllocationId']
  log('Elastic IP', eip_name)
  return AllocationId

def setup_nat_gateway(NGW_NAME, eip_id, subnet_id):
  client = boto3.client('ec2')
  response = client.describe_nat_gateways(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ NGW_NAME ]
      },
      {
        'Name' : "state",
        'Values' : ["available", "pending"]
      }
    ],
  )
  if response['NatGateways']:
    nat_gateway_id = response['NatGateways'][0]['NatGatewayId']
  else:
    nat_gateway = client.create_nat_gateway(
      AllocationId=eip_id,
      SubnetId = subnet_id,
      TagSpecifications=[
        {
          'ResourceType': 'natgateway',
          'Tags':[
            {
              "Key": "Name",
              "Value": NGW_NAME
            },
          ]
        }
      ]
    )
    nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']
    waiter = client.get_waiter('nat_gateway_available')
    waiter.wait(
      NatGatewayIds=[nat_gateway_id]
    )
  log('NAT Gateway', NGW_NAME)
  return nat_gateway_id

def delete_vpc(vpc_name):
  client = boto3.client('ec2')
  response = client.describe_vpcs(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ vpc_name ]
      }
    ]
  )
  if response['Vpcs']:
    client.delete_vpc(
      VpcId=response['Vpcs'][0]['VpcId']
    )
  log('VPC', vpc_name)

def delete_internet_gateway(igw_name):
  client = boto3.client('ec2')
  response = client.describe_internet_gateways(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ igw_name ]
      }
    ]
  )
  if response['InternetGateways']:
    if response['InternetGateways'][0]['Attachments']:
      internet_gateway_id = response['InternetGateways'][0]['InternetGatewayId']
      vpc_id = response['InternetGateways'][0]['Attachments'][0]['VpcId']

      client.detach_internet_gateway(
        InternetGatewayId=internet_gateway_id,
        VpcId=vpc_id
      )
    client.delete_internet_gateway(
      InternetGatewayId=internet_gateway_id
    )
  log("Internet Gateway", igw_name)

def delete_route_table(route_table_name):
  client = boto3.client('ec2')
  response = client.describe_route_tables(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ route_table_name ]
      }
    ]
  )
  if response['RouteTables']:
    if response['RouteTables'][0]['Associations']:
      for i in range(len(response['RouteTables'][0]['Associations'])):
        client.disassociate_route_table(
          AssociationId=response['RouteTables'][0]['Associations'][i]['RouteTableAssociationId']
        )  
    client.delete_route_table(
      RouteTableId=response['RouteTables'][0]['RouteTableId']
    )
  log('Route Table', route_table_name)

def delete_subnet(subnet_name):
  client = boto3.client('ec2')
  # check if subnet already exists.
  response = client.describe_subnets(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ subnet_name ]
      }
    ]
  )
  if response['Subnets']:
    client.delete_subnet(
      SubnetId=response['Subnets'][0]['SubnetId'])
  log('Subnet', subnet_name)

def delete_security_group(sg_name):
  client = boto3.client('ec2')
  response = client.describe_security_groups(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ sg_name ]
      }
    ]
  )
  if response['SecurityGroups']:
    client.delete_security_group(
      GroupId=response['SecurityGroups'][0]['GroupId']
    )
  log('Security Group', sg_name)

def delete_key_pair(key_pair_name):
  client = boto3.client('ec2')
  # create a file to store the key locally
  response = client.describe_key_pairs(
    Filters=[
      {
        'Name' : "key-name",
        "Values" : [ key_pair_name ]
      }
    ]
  )
  if response['KeyPairs']:
    client.delete_key_pair(
      KeyName=key_pair_name
    )
    if os.path.exists('{key_pair_name}.pem'):
      os.remove('{key_pair_name}.pem')
  log('Key Pair', key_pair_name)

def delete_instance(instance_name):
  client = boto3.client('ec2')
  response = client.describe_instances(
    Filters=[
      {
        'Name' : 'tag:Name',
        'Values' : [ instance_name ]
      },
      {
        'Name' : 'instance-state-name',
        'Values' : [ 'running', 'pending']
      }
    ]
  )
  if response['Reservations']:
    client.terminate_instances(
      InstanceIds=[response['Reservations'][0]['Instances'][0]['InstanceId']]
    )
    waiter = client.get_waiter('instance_terminated')
    waiter.wait(
      InstanceIds=[response['Reservations'][0]['Instances'][0]['InstanceId']]
    )
    log('EC2 Instance Deleted', instance_name)
  else:
    log('EC2 Instance Not Found', instance_name)

def delete_eip(eip_name):
  client = boto3.client('ec2')
  response = client.describe_addresses(
      Filters=[
          {
              'Name': 'tag:Name',
              'Values': [eip_name] 
          },
      ]
  )
  if response['Addresses']:
    client.release_address(
      AllocationId=response['Addresses'][0]['AllocationId']
    )
  log('Elastic IP', eip_name)

def delete_nat_gateway(NGW_NAME):
  client = boto3.client('ec2')
  response = client.describe_nat_gateways(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ NGW_NAME ]
      },
      {
        'Name' : "state",
        'Values' : ["available", "pending"]
      }
    ],
  )
  if response['NatGateways']:
    client.delete_nat_gateway(
      NatGatewayId=response['NatGateways'][0]['NatGatewayId']
    )
    wait_deleted_nat_gateway(response['NatGateways'][0]['NatGatewayId'])
  log('Nat Gateway', NGW_NAME)

def wait_deleted_nat_gateway(NGW_ID):
  client = boto3.client('ec2')
  response = client.describe_nat_gateways(
    NatGatewayIds=[NGW_ID]
  )
  while True:
    if response['NatGateways'][0]['State'] == 'deleted':
      break
    time.sleep(5)
    response = client.describe_nat_gateways(
      NatGatewayIds=[NGW_ID]
    )

def delete_listener(LB_NAME):
  client = boto3.client('elbv2')
  load_balancer_arn = get_load_balancer_arn(LB_NAME)
  if load_balancer_arn == None:
    return 0
  else:
    listener_arn = get_listener_arn(load_balancer_arn)
    if load_balancer_arn == None:
      return 0
    else:
      response = client.delete_listener(
        ListenerArn=listener_arn
      )
  log('Listener', LB_NAME)

def delete_load_balancer(LB_NAME):
  client = boto3.client('elbv2')
  try:
    response = client.describe_load_balancers(
      Names=[LB_NAME]
    )
  except ClientError as e:
    pass
  else:
    client.delete_load_balancer(
      LoadBalancerArn=response['LoadBalancers'][0]['LoadBalancerArn']
    )
  log('Load Balancer', LB_NAME)

def delete_target_group(LB_TARGET_NAME):
  client = boto3.client('elbv2')
  try:
    response = client.describe_target_groups(
      Names=[ LB_TARGET_NAME ]
    )
  except ClientError as e:
    pass
  else:
    client.delete_target_group(
      TargetGroupArn=response['TargetGroups'][0]['TargetGroupArn']
    )
  log('Target Group', LB_TARGET_NAME)

def setup_load_balancer(LB_NAME, subnet_1_id, subnet_2_id, security_group_id):
  client = boto3.client('elbv2')
  try:
    response = client.describe_load_balancers(
      Names=[LB_NAME]
    )
  except ClientError as e:
    response = client.create_load_balancer(
      Name=LB_NAME,
      Subnets=[ 
        subnet_1_id, 
        subnet_2_id 
      ],
      SecurityGroups=[ security_group_id ]
    )
    load_balancer_arn = response['LoadBalancers'][0]['LoadBalancerArn']
    waiter = client.get_waiter('load_balancer_available')
    waiter.wait(
      LoadBalancerArns=[load_balancer_arn]
    )
  else:
    load_balancer_arn = get_load_balancer_arn(LB_NAME)
  log('Load Balancer', LB_NAME)
  return load_balancer_arn

def setup_target_group(LB_TARGET_NAME, vpc):
  client = boto3.client('elbv2')
  try:
    response = client.describe_target_groups(
      Names=[ LB_TARGET_NAME ]
    )
  except ClientError as e:
    response = client.create_target_group(
        Name=LB_TARGET_NAME,
        Port=80,
        Protocol='HTTP',
        VpcId=vpc.id,
    )
  log('Target Group', LB_TARGET_NAME)
  return response['TargetGroups'][0]['TargetGroupArn']

def register_targets(target_group_arn, instance_1_id, instance_2_id):
  client = boto3.client('elbv2')
  response = client.register_targets(
      TargetGroupArn=target_group_arn,
      Targets=[
          {
              'Id': instance_1_id,
              'Port': 80,
          },
          {
              'Id': instance_2_id,
              'Port': 80,
          },
      ],
  )

def setup_listener(target_group_arn, loadbalancer_arn):
  client = boto3.client('elbv2')
  response = client.create_listener(
      DefaultActions=[
          {
              'TargetGroupArn': target_group_arn,
              'Type': 'forward',
          },
      ],
      LoadBalancerArn=loadbalancer_arn,
      Port=80,
      Protocol='HTTP',
      Tags=[
        {
            'Key': 'Name',
            'Value': 'ELBHTTPListener'
        },
    ]
  )

# Get ID / ARN functions
def get_load_balancer_arn(LB_NAME):
  client = boto3.client('elbv2')
  try:
    response = client.describe_load_balancers(
      Names=[LB_NAME]
    )
  except ClientError as e:
    return None
  else:
    return response['LoadBalancers'][0]['LoadBalancerArn']

def get_vpc_id(vpc_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  response = client.describe_vpcs(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ vpc_name ]
      }
    ]
  )
  if response['Vpcs']:
    vpc = ec2.Vpc(response['Vpcs'][0]['VpcId'])
    return vpc.id
  else:
    return '0'

def get_vpc(vpc_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  response = client.describe_vpcs(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ vpc_name ]
      }
    ]
  )
  if response['Vpcs']:
    vpc = ec2.Vpc(response['Vpcs'][0]['VpcId'])
    return vpc
  else:
    return None

def get_subnet(subnet_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')
  # check if subnet already exists.
  response = client.describe_subnets(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ subnet_name ]
      }
    ]
  )
  if response['Subnets']:
    subnet = ec2.Subnet(response['Subnets'][0]['SubnetId'])
    return subnet
  else:
    return None

def get_security_group(sg_name):
  client = boto3.client('ec2')
  ec2 = boto3.resource('ec2')

  response = client.describe_security_groups(
    Filters=[
      {
        'Name' : "tag:Name",
        "Values" : [ sg_name ]
      }
    ]
  )
  if response['SecurityGroups']:
    security_group = ec2.SecurityGroup(response['SecurityGroups'][0]['GroupId'])
    return security_group
  else:
    return None

def get_target_group_arn(LB_TARGET_NAME):
  client = boto3.client('elbv2')
  response = client.describe_target_groups(
    Names=[LB_TARGET_NAME]
  )
  if response['TargetGroups']:
    return response['TargetGroups'][0]['TargetGroupArn']
  else:
    return '0'

def get_listener_arn(LB_ARN):
  client = boto3.client('elbv2')
  response = client.describe_listeners(
    LoadBalancerArn=LB_ARN
  )
  if response['Listeners']:
    return response['Listeners'][0]['ListenerArn']
  else:
    return None

