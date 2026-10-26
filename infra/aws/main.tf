terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = {
      Project   = "capstone-fl-traffic"
      ManagedBy = "Terraform"
    }
  }
}

variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "account_id" {
  type        = string
  description = "Expected AWS account; prevents deploying to another account."
}

variable "ami_id" {
  type        = string
  description = "Canonical Ubuntu 24.04 x86_64 AMI in the selected region."
}

variable "subnet_id" {
  type        = string
  description = "Existing public subnet; no NAT gateway or new VPC is created."
}

variable "ssh_public_key_path" {
  type = string
}

variable "ssh_cidr" {
  type        = string
  description = "Current workstation public IPv4 address, with /32."
  validation {
    condition     = can(cidrnetmask(var.ssh_cidr)) && endswith(var.ssh_cidr, "/32")
    error_message = "Allow SSH from exactly one IPv4 address (/32)."
  }
}

data "aws_subnet" "public" {
  id = var.subnet_id
}

resource "aws_key_pair" "collector" {
  key_name   = "capstone-traffic-ssh"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_security_group" "collector" {
  name_prefix = "capstone-traffic-"
  description = "Traffic collector: SSH from owner; database stays private"
  vpc_id      = data.aws_subnet.public.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.collector.id
  cidr_ipv4         = var.ssh_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from the owner current public IP"
}

resource "aws_vpc_security_group_egress_rule" "outbound" {
  security_group_id = aws_security_group.collector.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_instance" "collector" {
  ami                                  = var.ami_id
  instance_type                        = "t3.small"
  subnet_id                            = var.subnet_id
  associate_public_ip_address          = true
  key_name                             = aws_key_pair.collector.key_name
  vpc_security_group_ids               = [aws_security_group.collector.id]
  instance_initiated_shutdown_behavior = "stop"
  user_data                            = file("${path.module}/bootstrap.sh")

  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = false
    tags                  = { Name = "capstone-traffic-data" }
  }

  tags = { Name = "capstone-traffic-collector" }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    aws_vpc_security_group_ingress_rule.ssh,
    aws_vpc_security_group_egress_rule.outbound,
  ]
}

output "instance_id" {
  value = aws_instance.collector.id
}

output "public_ip" {
  value = aws_instance.collector.public_ip
}

output "root_volume_id" {
  value = aws_instance.collector.root_block_device[0].volume_id
}
