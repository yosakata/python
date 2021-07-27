from my_functions import *

vpc_cidr="10.0.0.0/16"
subnet_cidr="10.0.1.0/24"
vpc_name="LinuxEnvVpc"
subnet_name="LinuxEnvPublic"
instance_name="RHEL8"
instance_type="m5.4xlarge"
igw_name="LinuxEnvIgw"
route_table_name="LinuxEnvRTPublic"
sg_name="LinuxEnvSg"
key_pair_name="LinuxEnvKeyPair"
eip_name="LinuxEnvEip"
region="us-west-2"
public_ip=True

available_zone_a="us-west-2a"
available_zone_b="us-west-2b"
available_zone_c="us-west-2c"

# Amazon Linux 2 for us-west-2 region
AMI="ami-083ac7c7ecf9bb9b0"

# RHEL8
AMI="ami-0b28dfc7adc325ef4"

userdata = """
#!/bin/bash
yum update -y
amazon-linux-extras install docker
usermod -a -G docker ec2-user
service docker start
yum install -y httpd
echo `hostname -I | awk '{print $1}'` > /var/www/html/index.html
systemctl enable httpd
systemctl start httpd
"""

#-------
# Main
#-------

# vpc = get_vpc(vpc_name=v)
# subnet = get_subnet(subnet_name)
# security_group = get_security_group(sg_name)

# Create VPC
vpc = setup_vpc(vpc_name=vpc_name, vpc_cidr=vpc_cidr)

# Create an internet gateway and attach it to VPC
internet_gateway = setup_internet_gateways(igw_name=igw_name, vpc=vpc)

# create a route table and add internet gateway to the table
route_table = setup_route_table(route_table_name, vpc, internet_gateway.id)

# create subnet and associate it with route table
subnet_pub = setup_subnet(subnet_name, subnet_cidr, available_zone_a, vpc, route_table)

# create a security group and allow SSH inbound rule through the 
security_group = setup_security_group(sg_name, vpc.id)

# allocationId = setup_eip(eip_name)
# Create KeyPair
# key_pair_name = setup_key_pair(key_pair_name)

instance = setup_instance(AMI, subnet_pub.id, security_group.group_id, instance_name, key_pair_name, userdata, instance_type, public_ip)

exit()


# Replace public ip address with elastic ip address

ec2 = boto3.client('ec2')

try:
    response = ec2.associate_address(AllocationId=allocationId,
                                     InstanceId=instance.id)
    print(response)
except ClientError as e:
    print(e)