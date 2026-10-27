"""Deploy the static dashboard to existing EC2 with HTTPS and cookie login."""
import argparse
import json
import os
from pathlib import Path
import hashlib
import secrets
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
INFRA=ROOT/'infra/aws'
IMAGE='caddy:2.11.7-alpine'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-dir',type=Path,required=True)
    args=parser.parse_args()
    if not (args.static_dir/'index.html').is_file():parser.error('Build static AWS frontend first')
    outputs=json.loads(subprocess.check_output([str(Path.home()/'.local/bin/terraform'),f'-chdir={INFRA}','output','-json']))
    host=outputs['public_ip']['value']
    options=['-i',str(Path.home()/'.ssh/capstone-traffic-aws'),'-o','IdentitiesOnly=yes',
        '-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={INFRA/".state/known_hosts"}']
    ssh=['ssh',*options,f'ubuntu@{host}']
    login_file=INFRA/'.state/web-login.json'
    if not login_file.exists():
        fd=os.open(login_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as file:json.dump({'username':'tuan','password':secrets.token_urlsafe(20),'url':f'https://{host}'},file)
    login=json.loads(login_file.read_text())
    auth_file=INFRA/'.state/web-auth.json'
    auth=json.loads(auth_file.read_text()) if auth_file.exists() else None
    valid=auth and auth['username']==login['username'] and secrets.compare_digest(
        hashlib.pbkdf2_hmac('sha256',login['password'].encode(),bytes.fromhex(auth['salt']),auth['iterations']).hex(),auth['password_hash'])
    if not valid:
        salt=secrets.token_bytes(32)
        auth={'username':login['username'],'salt':salt.hex(),'iterations':600000,
            'password_hash':hashlib.pbkdf2_hmac('sha256',login['password'].encode(),salt,600000).hex(),
            'session_key':secrets.token_hex(32)}
    auth['origin']=f'https://{host}'
    fd=os.open(auth_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as file:json.dump(auth,file)
    caddy='''{
    admin off
    default_sni HOST
}
https://HOST {
    tls {
        issuer acme {
            dir https://acme-v02.api.letsencrypt.org/directory
            profile shortlived
            disable_http_challenge
        }
    }
    encode zstd gzip
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        X-Frame-Options DENY
    }
    reverse_proxy web_auth:8080
}
'''.replace('HOST',host)
    archive=INFRA/'.state/web-deploy.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for path in sorted(args.static_dir.rglob('*')):
            if path.is_file():bundle.add(path,arcname='web/static/'+str(path.relative_to(args.static_dir)))
        for name in ['infra/aws/compose.web.yml','infra/aws/compose.dashboard.yml','dashboard/sync_site.py',
                     'infra/aws/Dockerfile.web-auth','dashboard/auth_server.py']:
            bundle.add(ROOT/name,arcname=name)
        bundle.add(ROOT/'dashboard/auth',arcname='dashboard/auth')
    subprocess.run(['scp',*options,str(archive),f'ubuntu@{host}:/tmp/web-deploy.tar.gz'],check=True)
    subprocess.run(ssh+['tar -xzf /tmp/web-deploy.tar.gz -C /opt/capstone-traffic; '
        'sudo mkdir -p /var/lib/capstone-traffic/web-snapshot /var/lib/capstone-traffic/caddy-data /var/lib/capstone-traffic/caddy-config'],check=True)
    subprocess.run(ssh+['umask 077; cat > /opt/capstone-traffic/web/Caddyfile'],input=caddy,text=True,check=True)
    subprocess.run(ssh+['umask 077; cat > /opt/capstone-traffic/web/auth.json'],input=json.dumps(auth),text=True,check=True)
    # This file contains no secrets. Root inside the container has no
    # DAC_OVERRIDE capability and must be able to read the ubuntu-owned mount.
    subprocess.run(ssh+['chmod 644 /opt/capstone-traffic/web/Caddyfile'],check=True)
    subprocess.run(ssh+[f'sudo docker run --rm --entrypoint caddy '
        '-v /opt/capstone-traffic/web/Caddyfile:/etc/caddy/Caddyfile:ro '
        f'{IMAGE} adapt --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null'],check=True)
    subprocess.run(ssh+['cd /opt/capstone-traffic && sudo docker compose -f docker-compose.yml '
        '-f infra/aws/compose.cloud.yml -f infra/aws/compose.dashboard.yml '
        'up -d --build dashboard_sync --wait'],check=True)
    subprocess.run(ssh+['cd /opt/capstone-traffic && sudo docker compose -f docker-compose.yml '
        '-f infra/aws/compose.cloud.yml -f infra/aws/compose.web.yml up -d --build --force-recreate web_auth web'],check=True)
    print(f'Deployed https://{host}; login stored privately at {login_file}')


if __name__=='__main__':main()
