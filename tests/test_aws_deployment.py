"""Offline AWS infrastructure safety and immutable source-release checks.

These do not call AWS, boot Linux, build a container or validate an AWS account.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AWS = ROOT / 'deploy' / 'aws'
spec = importlib.util.spec_from_file_location('aws_prepare_release', AWS / 'prepare_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class AWSDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.host = json.loads((AWS / 'workbench.template.json').read_text())
        self.storage = json.loads((AWS / 'storage.template.json').read_text())

    def test_retained_private_encrypted_storage(self):
        bucket = self.storage['Resources']['Artifacts']
        self.assertEqual(bucket['DeletionPolicy'], 'Retain')
        props = bucket['Properties']
        self.assertEqual(props['VersioningConfiguration']['Status'], 'Enabled')
        self.assertTrue(all(props['PublicAccessBlockConfiguration'].values()))
        encryption = props['BucketEncryption']['ServerSideEncryptionConfiguration'][0]
        self.assertEqual(encryption['ServerSideEncryptionByDefault']['SSEAlgorithm'], 'AES256')
        policy = self.storage['Resources']['RequireTLS']['Properties']['PolicyDocument']
        self.assertEqual(policy['Statement'][0]['Effect'], 'Deny')
        self.assertEqual(policy['Statement'][0]['Condition']['Bool']['aws:SecureTransport'], 'false')
        volume = self.host['Resources']['DataVolume']
        self.assertEqual(volume['DeletionPolicy'], 'Retain')
        self.assertTrue(volume['Properties']['Encrypted'])

    def test_no_inbound_ports_and_imdsv2_required(self):
        # The larger retained options are not eligible Free Plan defaults.
        self.assertEqual(self.host['Parameters']['InstanceType']['Default'], 't3.small')
        resources = self.host['Resources']
        self.assertFalse(resources['AppSecurityGroup']['Properties'].get('SecurityGroupIngress'))
        instance = resources['AppInstance']['Properties']
        self.assertEqual(instance['MetadataOptions']['HttpTokens'], 'required')
        self.assertTrue(instance['BlockDeviceMappings'][0]['Ebs']['Encrypted'])
        self.assertEqual(instance['CreditSpecification']['CPUCredits'], 'standard')
        script = (AWS / 'bootstrap.sh').read_text()
        self.assertIn('BIOGRAPH_HOST=127.0.0.1', script)
        self.assertIn('BIOGRAPH_PORT=8766', script)

    def test_volume_attachment_does_not_wait_on_its_own_bootstrap_signal(self):
        resources = self.host['Resources']
        self.assertNotIn('CreationPolicy', resources['AppInstance'])
        self.assertEqual(resources['DataAttachment']['Properties']['InstanceId'], {'Ref': 'AppInstance'})
        ready = resources['BootstrapReady']
        self.assertEqual(ready['Type'], 'AWS::CloudFormation::WaitCondition')
        self.assertEqual(ready['DependsOn'], 'DataAttachment')
        self.assertEqual(ready['CreationPolicy']['ResourceSignal']['Count'], 1)
        self.assertNotIn('Properties', ready)  # No presigned handle in user data.

    def test_instance_role_reads_exact_release_and_only_its_backup_prefix(self):
        props = self.host['Resources']['InstanceRole']['Properties']
        statements = props['Policies'][0]['PolicyDocument']['Statement']
        exact = next(s for s in statements if s['Sid'] == 'ReadExactRelease')
        backups = next(s for s in statements if s['Sid'] == 'OwnWorkspaceBackups')
        self.assertEqual(exact['Resource']['Fn::Sub'],
                         'arn:${AWS::Partition}:s3:::${ArtifactBucket}/${ArtifactKey}')
        self.assertEqual(backups['Resource']['Fn::Sub'],
                         'arn:${AWS::Partition}:s3:::${ArtifactBucket}/backups/${AWS::StackName}/*')
        self.assertNotIn('s3:DeleteObject', backups['Action'])
        self.assertNotIn('s3:*', json.dumps(props))

    def test_bootstrap_and_rendered_user_data_have_valid_shell_syntax(self):
        for filename in ('bootstrap.sh', 'backup.sh'):
            subprocess.run(['bash', '-n', str(AWS / filename)], check=True, capture_output=True)
        join = self.host['Resources']['AppInstance']['Properties']['UserData']['Fn::Base64']['Fn::Join']
        self.assertEqual(join[0], '')
        script = ''.join(part if isinstance(part, str) else 'invented-safe-value' for part in join[1])
        subprocess.run(['bash', '-n'], input=script, text=True, check=True, capture_output=True)
        self.assertLess(script.index('sha256sum --check'), script.index('tar -xzf'))
        self.assertIn('--logical-resource-id BootstrapReady', script)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', script)


class NeptuneDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((AWS / 'neptune.template.json').read_text())
        self.resources = self.template['Resources']

    def test_private_production_class_cluster_and_recoverable_storage(self):
        cluster = self.resources['NeptuneCluster']
        self.assertEqual(cluster['DeletionPolicy'], 'Snapshot')
        self.assertEqual(cluster['UpdateReplacePolicy'], 'Snapshot')
        props = cluster['Properties']
        self.assertTrue(props['IamAuthEnabled'])
        self.assertTrue(props['StorageEncrypted'])
        self.assertTrue(props['DeletionProtection'])
        self.assertEqual(props['BackupRetentionPeriod'], 7)
        self.assertNotIn('Default', self.template['Parameters']['EngineVersion'])
        for name in ('WriterInstance', 'ReaderInstance'):
            instance = self.resources[name]['Properties']
            self.assertEqual(instance['DBInstanceClass'], 'db.r6g.large')
            self.assertFalse(instance['PubliclyAccessible'])
        self.assertEqual(self.template['Parameters']['EnableReader']['Default'], 'false')
        self.assertEqual(self.resources['ReaderInstance']['Condition'], 'MakeReader')
        self.assertEqual(len(self.resources['DbSubnetGroup']['Properties']['SubnetIds']), 2)
        self.assertIn('DistinctSubnets', self.template['Rules'])

    def test_8182_is_scoped_to_app_group_in_both_directions(self):
        inbound = self.resources['AppToNeptuneIngress']['Properties']
        outbound = self.resources['AppToNeptuneEgress']['Properties']
        for rule in (inbound, outbound):
            self.assertEqual((rule['FromPort'], rule['ToPort']), (8182, 8182))
            self.assertNotIn('CidrIp', rule)
            self.assertNotIn('CidrIpv6', rule)
        self.assertEqual(inbound['SourceSecurityGroupId'], {'Ref': 'AppSecurityGroupId'})
        self.assertEqual(outbound['DestinationSecurityGroupId'], {'Ref': 'NeptuneSecurityGroup'})

    def test_query_reads_and_health_survive_import_permission_revocation(self):
        normal = self.resources['AppReadOnlyPolicy']
        self.assertNotIn('Condition', normal)
        statements = normal['Properties']['PolicyDocument']['Statement']
        self.assertEqual({s['Action'] for s in statements},
                         {'neptune-db:ReadDataViaQuery', 'neptune-db:GetEngineStatus'})
        read = next(s for s in statements if s['Action'].endswith('ReadDataViaQuery'))
        self.assertEqual(read['Condition']['StringEquals']['neptune-db:QueryLanguage'], 'OpenCypher')
        health = next(s for s in statements if s['Action'].endswith('GetEngineStatus'))
        self.assertNotIn('Condition', health)  # No query-language context on status requests.
        for statement in statements:
            self.assertIn('${NeptuneCluster.ClusterResourceId}/*', statement['Resource']['Fn::Sub'])
        self.assertEqual(self.template['Parameters']['AllowInitialGraphImport']['Default'], 'false')
        temporary = self.resources['InitialGraphImportPolicy']
        self.assertEqual(temporary['Condition'], 'InitialImport')
        actions = {action for s in temporary['Properties']['PolicyDocument']['Statement']
                   for action in (s['Action'] if isinstance(s['Action'], list) else [s['Action']])}
        self.assertIn('neptune-db:StartLoaderJob', actions)
        self.assertIn('neptune-db:WriteDataViaQuery', actions)
        self.assertNotIn('neptune-db:DeleteDataViaQuery', actions)
        self.assertNotIn('neptune-db:ResetDatabase', actions)

    def test_loader_s3_read_scope_and_gateway_route_are_separate_from_app_upload(self):
        role = self.resources['NeptuneLoaderRole']['Properties']
        statements = role['Policies'][0]['PolicyDocument']['Statement']
        actions = {a for s in statements for a in (s['Action'] if isinstance(s['Action'], list) else [s['Action']])}
        self.assertEqual(actions, {'s3:GetBucketLocation', 's3:ListBucket', 's3:GetObject', 's3:GetObjectVersion'})
        listed = next(s for s in statements if s['Action'] == 's3:ListBucket')
        self.assertEqual(listed['Condition']['StringLike']['s3:prefix'], {'Fn::Sub': '${GraphObjectPrefix}*'})
        objects = next(s for s in statements if isinstance(s['Action'], list))
        self.assertEqual(objects['Resource']['Fn::Sub'],
                         'arn:${AWS::Partition}:s3:::${ArtifactBucket}/${GraphObjectPrefix}*')
        gateway = self.resources['S3GatewayEndpoint']
        self.assertEqual(gateway['Condition'], 'MakeS3Endpoint')
        self.assertEqual(gateway['Properties']['VpcEndpointType'], 'Gateway')
        self.assertEqual(gateway['Properties']['RouteTableIds'], {'Ref': 'S3RouteTableIds'})
        self.assertEqual(gateway['Properties']['ServiceName'], {'Fn::Sub': 'com.amazonaws.${AWS::Region}.s3'})


class SourceReleaseTests(unittest.TestCase):
    def fixture(self, root):
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        for name in release.RUNTIME_PATHS:
            path = root / name
            if name in ('biograph_steward', 'scripts'):
                path = path / 'invented.py'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('invented runtime source\n')
        for name in ('.env', 'runs/private.json', '.pharos_cache/private.json'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('invented excluded private data\n')
        self.commit(root)

    def commit(self, root):
        subprocess.run(['git', 'add', '.'], cwd=root, check=True)
        subprocess.run(['git', '-c', 'user.name=Offline test', '-c', 'user.email=offline@example.invalid',
                        'commit', '-qm', 'fixture'], cwd=root, check=True)

    def test_committed_bundle_is_repeatable_and_excludes_local_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / 'repo'
            self.fixture(root)
            first = release.prepare(base / 'one', root=root)
            second = release.prepare(base / 'two', root=root)
            self.assertEqual(first['sha256'], second['sha256'])
            with tarfile.open(base / 'one' / first['bundle']) as archive:
                names = archive.getnames()
            self.assertIn('deploy/aws/bootstrap.sh', names)
            self.assertIn('requirements-aws.txt', names)
            self.assertNotIn('.env', names)
            self.assertFalse(any(name.startswith(('runs/', '.pharos_cache/')) for name in names))
            with self.assertRaises(ValueError):
                release.prepare(base / 'one', root=root)

    def test_runtime_symlink_is_rejected_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / 'repo'
            self.fixture(root)
            (root / 'scripts' / 'link.py').symlink_to('../.env')
            self.commit(root)
            with self.assertRaisesRegex(ValueError, 'link'):
                release.prepare(base / 'rejected', root=root)
            self.assertFalse((base / 'rejected').exists())


if __name__ == '__main__':
    unittest.main()
