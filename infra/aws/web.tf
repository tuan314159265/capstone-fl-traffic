resource "aws_vpc_security_group_ingress_rule" "web_http" {
  security_group_id = aws_security_group.collector.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "ACME IP certificate validation and HTTPS redirect"
}

resource "aws_vpc_security_group_ingress_rule" "web_https" {
  security_group_id = aws_security_group.collector.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Private traffic dashboard over HTTPS with authentication"
}
