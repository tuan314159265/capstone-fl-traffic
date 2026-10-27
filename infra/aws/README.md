# AWS collector

One Ubuntu 24.04 x86_64 EC2 `t3.small` in Sydney (`ap-southeast-2`), with
2 vCPU, 2 GiB RAM, 2 GiB swap, and an encrypted 20 GiB gp3 EBS root disk.
The existing default VPC is reused. No RDS, NAT gateway, load balancer, GPU,
Elastic IP, or AWS access key on the server is needed.

## Files and credentials

- `main.tf`: EC2, SSH key pair and security group. Only SSH from `ssh_cidr` is
  allowed inbound; PostGIS is bound to localhost port 54329.
- `bootstrap.sh`: installs Docker and Compose on Ubuntu.
- `compose.cloud.yml` and `Dockerfile.collector`: PostGIS and a small Python
  collector image, without training dependencies.
- `deploy.py`: uploads only the required files and installs systemd timers.
- `terraform.tfvars.json`: local account, AMI, subnet, SSH public key and source IP.
- `.state/cloud.env`: private TomTom keys and separately generated DB password.
- `.state/stop-at-utc.txt`: fixed stop deadline, 28 days after the first deployment.

Terraform state, variable files, deployment archives and `.state/` are ignored by
Git. Keep private backups of Terraform state and the SSH private key at
`~/.ssh/capstone-traffic-aws`. No API keys or passwords are passed through
Terraform, EC2 user data, or the Docker image. Only the TomTom key is copied from
the project's original `.env`; the second account uses `API_TOMTOM_TRAFFIC`.
Unrelated provider keys are not uploaded.

## Deploy and update

From `infra/aws`, after configuring `terraform.tfvars.json`:

```bash
terraform init
terraform validate
terraform plan -out=collector.tfplan
terraform apply collector.tfplan
```

From the repository root, after `.state/cloud.env` has been prepared:

```bash
python infra/aws/deploy.py
```

The deploy script uploads the current collector, rebuilds its image, starts
PostGIS, installs timers, collects one snapshot and verifies persisted records.
Re-running it preserves the existing database, request counter and stop deadline.

Get the current public IP with `terraform -chdir=infra/aws output -raw public_ip`.
It can change after stopping and starting the EC2 instance. If your workstation's
public IP changes, update `ssh_cidr` in the variable file and apply the reviewed
Terraform plan before connecting again.

## Import an earlier local collection day

From the repository root, with the local Docker DB running:

```bash
python infra/aws/import_local.py --date 2026-10-25 --verify-idempotency
```

Dates use `Asia/Ho_Chi_Minh`. The importer backs up both databases, exports the
selected day in one source snapshot, and merges its observations and referenced
metadata into AWS in one transaction. Source observations are not removed.
Numeric IDs are remapped using provider/segment hash, and original timestamps and
all measurements/raw JSON are verified. Existing query-point coordinates must
match. Repeated imports skip observations with the same provider, query point,
segment, collection timestamp and source timestamp; conflicting values abort the
transaction. `--verify-idempotency` repeats the merge and verifies zero new rows.

Private source exports, before/after backups and a receipt are saved under
`.state/import-DATE-TIMESTAMP/`, excluded from Git. The import performs no TomTom
API calls and does not consume its request budget. The initial migration of
2026-10-25 imported 228 observations from 16 query points.

## Collection and budget

`capstone-collector.timer` runs at every UTC quarter-hour. Each invocation runs
two fixed groups sequentially: 15 Ben Thanh points with `API_TOMTOM`, and 15
additional HCMC points with `API_TOMTOM_TRAFFIC`. Requests within a group use four
workers. Group definitions are in `collection_groups.json`. A failed
invocation is retried at the next quarter-hour; requests are not retried in a
tight restart loop. Points commit independently so one bad point does not discard
the other observations. Coordinates remain pilot candidates: validate returned
road geometries, direction, and duplicate segments before training.

TomTom's public pricing on 2026-10-26 lists 20,000 free monthly Flow Segment Data
requests. Fifteen points every 15 minutes need 1,440 requests/day and 43,200 per
30 days. The VM therefore defaults to a conservative **18,000 attempted requests
per UTC calendar month**, persisted in `/var/lib/capstone-traffic/request-budget.json`.
It reserves 15 before each invocation, including failed invocations. Once the
limit is reached it pauses until the next UTC month. This permits about 12.5 days
of quarter-hour sampling in a full calendar month, not uninterrupted four-week
sampling. Usage by other machines or applications is not included in this local
counter. The second group has an independent counter in
`/var/lib/capstone-traffic/request-budget-traffic.json`, configured by
`TOMTOM_TRAFFIC_MONTHLY_REQUEST_BUDGET` (also 18,000 by default). It includes the
22 initial coverage probes exactly once. The original counter is preserved.
Verify actual allowance/reset dates in each account dashboard before
increasing the limit. A 40-minute cadence needs about 16,200 requests/30 days.

To change budget, edit the private server `.env`. To change cadence, edit
`/etc/systemd/system/capstone-collector.timer` and run `systemctl daemon-reload`
followed by `systemctl restart capstone-collector.timer`. Keep node IDs and cadence
stable for each experimental collection period; document any change.

## Operations

After SSH login:

```bash
sudo systemctl list-timers 'capstone-*' --no-pager
sudo journalctl -u capstone-collector.service -n 60 --no-pager
cd /opt/capstone-traffic
sudo docker compose ps
sudo docker compose exec -T db psql -U capstone -d capstone_traffic \
  -c 'SELECT count(*), count(DISTINCT query_point_id), max(collected_at) FROM traffic_observations;'
```

The DB container restarts after reboot. Systemd timers are enabled and persistent.
Daily custom-format `pg_dump` backups are written to
`/var/backups/capstone-traffic/`, retaining seven days. These backups share the
same disk as the database; copy them off the VM for protection against disk loss.

For a local DB connection, forward localhost through SSH:

```bash
ssh -i ~/.ssh/capstone-traffic-aws -L 54330:127.0.0.1:54329 ubuntu@PUBLIC_IP
```

Use the separately generated cloud DB credentials from `.state/cloud.env`.

## Cost and automatic stop

AWS Sydney public list prices checked on 2026-10-26:

| Resource | List rate | Approximately 28 days |
| --- | --- | --- |
| Linux `t3.small` | USD 0.0264/hour | USD 17.74 |
| gp3 disk, 20 GiB | USD 0.096/GB-month | USD 1.79 |
| One public IPv4 | USD 0.005/hour | USD 3.36 |
| Total before credits, taxes, and additional network usage | | **USD 22.89** |

Free-tier eligibility is not proof of an available credit balance. The deployed
account's credit balance has not been verified. CPU credit mode is Standard,
preventing T3 Unlimited surplus-credit charges. Under sustained CPU load the VM
can throttle; this machine is intended for collection, not model training.

`capstone-expiry.timer` backs up and shuts down Ubuntu at the recorded deadline;
EC2 is configured to **stop**, retaining data. EBS storage continues to cost money
while stopped. Before deliberately extending collection, review credit and API
allowance, then adjust the expiry timer. Do not merely reboot after the deadline:
the persistent expired timer will stop the machine again.

Terraform `prevent_destroy` blocks accidental instance replacement/deletion.
The root volume also has `delete_on_termination=false`. To remove resources,
first export the data, deliberately remove that Terraform protection and review
the destroy plan. Retained EBS disks must be deleted separately when no longer
needed; terminating EC2 alone does not delete them.

Sources:

- [AWS project regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html)
- [EC2 Sydney public price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-southeast-2/index.csv)
- [Public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [TomTom pricing](https://docs.tomtom.com/pricing)

The private map dashboard and its read-only PostGIS synchronization are described
in [docs/10_DASHBOARD.md](../../docs/10_DASHBOARD.md). Its AWS container is limited
to 192 MiB/0.25 CPU and opens no inbound network ports.
