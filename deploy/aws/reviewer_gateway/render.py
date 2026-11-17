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
from importlib.util import module_from_spec, spec_from_file_location

HERE = Path(__file__).resolve().parent
_public_spec = spec_from_file_location('reviewer_gateway_public_demo', HERE / 'public_demo.py')
public = module_from_spec(_public_spec)
_public_spec.loader.exec_module(public)
RFC1918 = tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
IMAGE = re.compile(r'[0-9]{12}\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com/[a-z0-9][a-z0-9_./-]*@sha256:[a-f0-9]{64}')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def render(upstream_ip, output, *, gateway_image=None, vpc_id=None, subnet_a=None,
           subnet_b=None, app_security_group=None, public_demo=False, public_scope=None,
           ssm_parameter_arn=None):
    ip = ipaddress.IPv4Address(upstream_ip)
    if not any(ip in network for network in RFC1918):
        raise ValueError('Use the verified app host RFC1918 private IPv4 address, never loopback/public/metadata.')
    if type(public_demo) is not bool:
        raise ValueError('Public-demo mode is an explicit boolean option.')
    scope = None
    if public_demo:
        if public_scope is None:
            raise ValueError('Public mode requires a reviewed exact snapshot/GET scope JSON.')
        scope = public.load_scope(public_scope)
        public.validate_ui_contract(HERE.parents[2])
    elif public_scope is not None or ssm_parameter_arn is not None:
        raise ValueError('A public snapshot or SSM token ARN requires explicit --public-demo mode.')
    if ssm_parameter_arn is not None and (not isinstance(ssm_parameter_arn, str) or re.fullmatch(
            r'arn:aws:ssm:us-east-2:[0-9]{12}:parameter/[A-Za-z0-9_./-]+', ssm_parameter_arn) is None):
        raise ValueError('Use an exact public-backend SecureString parameter ARN in us-east-2.')
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
        if public_demo and not ssm_parameter_arn:
            raise ValueError('Public deployment parameters require the separate public-backend SSM token ARN.')
        if public_demo and ssm_parameter_arn.split(':')[4] != gateway_image.split('.')[0]:
            raise ValueError('Use the same owned AWS account for the public token and gateway image.')
    lock = json.loads((HERE / 'image.lock.json').read_text())
    base = lock['image']
    if re.fullmatch(r'nginx:1\.30\.6-alpine@sha256:[a-f0-9]{64}', base) is None:
        raise ValueError('Unreviewed NGINX base image lock.')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a fresh output directory; existing packets are never overwritten.')
    output.mkdir(parents=True, mode=0o700)
    nginx = (HERE / ('nginx.public.conf.in' if public_demo else 'nginx.conf.in')).read_text()
    if public_demo:
        nginx = nginx.replace('__PUBLIC_MAPS__', public.maps(scope)).replace('__PUBLIC_SUBFILTERS__', public.ui_subfilters())
    (output / 'nginx.conf').write_text(nginx.replace('__UPSTREAM_IPV4__', str(ip)))
    dockerfile = 'Dockerfile.public.in' if public_demo else 'Dockerfile.in'
    (output / 'Dockerfile').write_text((HERE / dockerfile).read_text().replace('__NGINX_IMAGE__', base))
    for name in ('gateway.template.json', 'registry.template.json', 'image.lock.json', 'alb_attributes.json'):
        shutil.copyfile(HERE / name, output / name)
    if public_demo:
        (output / 'gateway.template.json').write_text(json.dumps(public.cloud_template((HERE / 'gateway.template.json').read_text()), indent=2) + '\n')
        shutil.copyfile(HERE / 'public-entrypoint.sh', output / 'public-entrypoint.sh')
        (output / 'public_scope.json').write_text(json.dumps(scope, indent=2) + '\n')
    if gateway_image:
        parameters = [{'ParameterKey': key, 'ParameterValue': value} for key, value in (
            ('VpcId', vpc_id), ('PublicSubnetA', subnet_a), ('PublicSubnetB', subnet_b),
            ('ExistingAppSecurityGroupId', app_security_group), ('GatewayImage', gateway_image))]
        if public_demo:
            parameters.extend([{'ParameterKey': 'PublicDemoEnabled', 'ParameterValue': 'true'},
                               {'ParameterKey': 'SSMParameterARN', 'ParameterValue': ssm_parameter_arn}])
        (output / 'gateway.parameters.json').write_text(json.dumps(parameters, indent=2) + '\n')
    inventory = {path.name: {'bytes': path.stat().st_size, 'sha256': sha(path)}
                 for path in sorted(output.iterdir()) if path.is_file()}
    receipt = {'format': 'biograph-steward.reviewer-gateway-preparation.v1',
               'created_at': datetime.now(timezone.utc).isoformat(), 'upstream_ip': str(ip),
               'upstream_port': 8768 if public_demo else 8766, 'listen_port': 8080, 'base_image': base,
               'target_platform': 'linux/amd64', 'proxy_timeout_seconds': 600,
               'deployment_parameters_prepared': bool(gateway_image),
               'aws_calls': 0, 'resources_created': False, 'public_endpoint_ready': False,
               'files': inventory}
    if public_demo:
        receipt.update({'public_demo': True, 'public_snapshot_id': scope['snapshot_id'],
                        'public_snapshot_inventory_sha256': scope['snapshot_inventory_sha256'],
                        'public_snapshot_verified_by_renderer': False,
                        'public_run_ids': scope['run_ids'], 'public_get_paths': len(scope['get_paths']),
                        'public_post_paths': list(public.POST_PATHS),
                        'token_value_read_or_written': False, 'SSM_parameter_ARN': ssm_parameter_arn,
                        'backend_authentication_required': True, 'separate_public_backend_required': True})
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
    parser.add_argument('--public-demo', action='store_true', help='Prepare the separate scoped anonymous saved-replay gateway.')
    parser.add_argument('--public-scope', type=Path, help='Reviewed read-only public snapshot inventory pin, IDs and exact GET paths.')
    parser.add_argument('--ssm-parameter-arn', help='Existing SecureString ARN for only the separate public backend token, not a secret value.')
    args = parser.parse_args()
    receipt = render(args.upstream_ip, args.out, gateway_image=args.gateway_image, vpc_id=args.vpc_id,
                     subnet_a=args.subnet_a, subnet_b=args.subnet_b, app_security_group=args.app_security_group,
                     public_demo=args.public_demo, public_scope=args.public_scope, ssm_parameter_arn=args.ssm_parameter_arn)
    print(json.dumps({'prepared': True, 'out': str(args.out), 'files': len(receipt['files']),
                      'aws_calls': 0, 'resources_created': False}))

if __name__ == '__main__':
    main()
