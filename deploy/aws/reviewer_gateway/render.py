#!/usr/bin/env python3
"""Prepare a fresh local gateway build/deployment packet. No AWS calls."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
RFC1918 = tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
IMAGE = re.compile(r'[0-9]{12}\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com/[a-z0-9][a-z0-9_./-]*@sha256:[a-f0-9]{64}')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def render(upstream_ip, output, *, gateway_image=None, vpc_id=None, subnet_a=None,
           subnet_b=None, app_security_group=None):
    ip = ipaddress.IPv4Address(upstream_ip)
    if not any(ip in network for network in RFC1918):
        raise ValueError('Use the verified app host RFC1918 private IPv4 address, never loopback/public/metadata.')
    deployment = [gateway_image, vpc_id, subnet_a, subnet_b, app_security_group]
    if any(value is not None for value in deployment):
        if not all(isinstance(value, str) and value for value in deployment):
            raise ValueError('Deployment parameters require image, VPC, two subnets and app security group together.')
        match = IMAGE.fullmatch(gateway_image)
        if not match or match[1] != 'us-east-2':
            raise ValueError('Use an immutable private ECR image digest in the reviewed us-east-2 region.')
        for value, pattern in [(vpc_id, r'vpc-[a-f0-9]{8,17}'), (subnet_a, r'subnet-[a-f0-9]{8,17}'),
                               (subnet_b, r'subnet-[a-f0-9]{8,17}'), (app_security_group, r'sg-[a-f0-9]{8,17}')]:
            if re.fullmatch(pattern, value) is None:
                raise ValueError('Invalid resource identifier.')
        if subnet_a == subnet_b:
            raise ValueError('Supply two different subnets; verify their AZs, VPC and routes separately.')
    lock = json.loads((HERE / 'image.lock.json').read_text())
    base = lock['image']
    if re.fullmatch(r'nginx:1\.30\.6-alpine@sha256:[a-f0-9]{64}', base) is None:
        raise ValueError('Unreviewed NGINX base image lock.')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a fresh output directory; existing packets are never overwritten.')
    output.mkdir(parents=True, mode=0o700)
    (output / 'nginx.conf').write_text((HERE / 'nginx.conf.in').read_text().replace('__UPSTREAM_IPV4__', str(ip)))
    (output / 'Dockerfile').write_text((HERE / 'Dockerfile.in').read_text().replace('__NGINX_IMAGE__', base))
    for name in ('gateway.template.json', 'registry.template.json', 'image.lock.json', 'alb_attributes.json'):
        shutil.copyfile(HERE / name, output / name)
    if gateway_image:
        parameters = [{'ParameterKey': key, 'ParameterValue': value} for key, value in (
            ('VpcId', vpc_id), ('PublicSubnetA', subnet_a), ('PublicSubnetB', subnet_b),
            ('ExistingAppSecurityGroupId', app_security_group), ('GatewayImage', gateway_image))]
        (output / 'gateway.parameters.json').write_text(json.dumps(parameters, indent=2) + '\n')
    inventory = {path.name: {'bytes': path.stat().st_size, 'sha256': sha(path)}
                 for path in sorted(output.iterdir()) if path.is_file()}
    receipt = {'format': 'biograph-steward.reviewer-gateway-preparation.v1',
               'created_at': datetime.now(timezone.utc).isoformat(), 'upstream_ip': str(ip),
               'upstream_port': 8766, 'listen_port': 8080, 'base_image': base,
               'target_platform': 'linux/amd64', 'proxy_timeout_seconds': 600,
               'deployment_parameters_prepared': bool(gateway_image),
               'aws_calls': 0, 'resources_created': False, 'public_endpoint_ready': False,
               'files': inventory}
    receipt['content_sha256'] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (output / 'preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for path in output.iterdir():
        path.chmod(0o600)
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-ip', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--gateway-image')
    parser.add_argument('--vpc-id')
    parser.add_argument('--subnet-a')
    parser.add_argument('--subnet-b')
    parser.add_argument('--app-security-group')
    args = parser.parse_args()
    receipt = render(args.upstream_ip, args.out, gateway_image=args.gateway_image, vpc_id=args.vpc_id,
                     subnet_a=args.subnet_a, subnet_b=args.subnet_b, app_security_group=args.app_security_group)
    print(json.dumps({'prepared': True, 'out': str(args.out), 'files': len(receipt['files']),
                      'aws_calls': 0, 'resources_created': False}))

if __name__ == '__main__':
    main()
