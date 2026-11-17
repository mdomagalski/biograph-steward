"""Portable delivery checks use invented records and an injected tiny runtime."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_judge_demo as delivery

from biograph_steward.client import digest
from biograph_steward.assay_attachment import attach_assay
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_decisions, load_packet
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, verify_answer
from biograph_steward.reviews import read_run
from test_assay_attachment import cohort_snapshot, make_publication


COMMIT = '0123456789abcdef0123456789abcdef01234567'
NATIVE_MARKER = b'INVENTED_NATIVE_RECORD_MUST_NOT_ENTER_SOFTWARE'
RUNTIME_FILES = {
    'app.py': b'# Invented runtime fixture; no native input records.\n',
    'LICENSE': b'MIT software fixture\n',
    'biograph_steward/__init__.py': b'"""Invented packaged runtime."""\n',
}


def read(path):
    return json.loads(Path(path).read_text())


def tiny_runtime(output, ref):
    """Replace git/archive work with a known, locally verified source tarball."""
    output.mkdir(parents=True)
    bundle = output / 'source.tar.gz'
    with tarfile.open(bundle, 'w:gz') as archive:
        for name, content in RUNTIME_FILES.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    with tarfile.open(bundle, 'r:gz') as archive:
        actual = {member.name: archive.extractfile(member).read()
                  for member in archive.getmembers()}
    if actual != RUNTIME_FILES:
        raise AssertionError('Invented runtime tarball differs from its fixture.')
    return bundle, COMMIT


class JudgeDeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.run, self.packet, self.out = (self.root / name for name in
                                          ('source_run', 'packet', 'delivery'))
        snapshot = demo_snapshot()
        snapshot['targets'][0]['diseaseAssociationDetails'][0]['evidence'] = NATIVE_MARKER.decode()
        snapshot.pop('content_sha256')
        snapshot['content_sha256'] = digest(snapshot)
        self.graph = save_run(snapshot, self.run)
        self.manifest = export_packet(self.run, self.packet)

    def prepare(self, **changes):
        options = dict(ref='invented-release', runtime_builder=tiny_runtime)
        options.update(changes)
        # Any accidental use of the real source builder would consult git.
        with patch.object(delivery, 'prepare_source_release',
                          side_effect=AssertionError('No live source/git release in tests')):
            return delivery.prepare(self.packet, self.out, **options)

    def test_separate_archives_reopen_full_baseline_workspace_and_saved_answer(self):
        before_packet = delivery.inventory(self.packet)
        before_run = delivery.inventory(self.run)
        result = self.prepare()

        self.assertEqual(result, read(self.out / 'delivery.json'))
        self.assertEqual(result['content_sha256'], digest({k: v for k, v in result.items()
                                                          if k != 'content_sha256'}))
        self.assertEqual(result['source_packet_id'], self.manifest['packet_id'])
        self.assertEqual(result['git_commit'], COMMIT)
        self.assertEqual(result['counts'], self.manifest['counts'])
        self.assertEqual(result['decisions']['abstain'], len(self.graph['edges']))
        self.assertEqual(result['decisions']['keep'], 0)
        self.assertEqual(result['decisions']['prune'], 0)
        for field in ('source_data_in_software_archive', 'local_data_redistribution_cleared',
                      'cloud_resources_created', 'independent_biological_validation'):
            self.assertFalse(result[field])
        self.assertEqual((result['source_fetches'], result['model_calls']), (0, 0))

        software_zip = self.out / result['software_archive']['file']
        local_zip = self.out / result['local_data_archive']['file']
        self.assertEqual(sha(software_zip), result['software_archive']['sha256'])
        self.assertEqual(sha(local_zip), result['local_data_archive']['sha256'])
        with zipfile.ZipFile(software_zip) as archive:
            self.assertEqual(set(archive.namelist()), {*RUNTIME_FILES, 'README_DEMO.md'})
            for name in archive.namelist():
                self.assertNotIn(NATIVE_MARKER, archive.read(name))
                self.assertFalse({'runs', 'handoff', 'raw_responses', '.git'} & set(Path(name).parts))
            self.assertIn(b'no retrieved source data', archive.read('README_DEMO.md'))

        extracted = self.root / 'extracted'
        with zipfile.ZipFile(local_zip) as archive:
            archive.extractall(extracted)
        baseline = extracted / 'handoff/baseline_packet'
        verified, original = load_packet(baseline)
        report, retained = load_decisions(extracted / 'handoff')
        workspace = extracted / 'runs' / delivery.RUN_ID
        reopened = read_run(workspace)[2]
        self.assertEqual(verified['packet_id'], self.manifest['packet_id'])
        self.assertEqual(delivery.inventory(baseline), before_packet)
        self.assertEqual(original, self.graph)
        self.assertEqual(reopened, self.graph)
        for key in ('nodes', 'edges', 'assertions'):
            self.assertEqual(retained[key], reopened[key])
        self.assertEqual(report['counts']['abstain'], len(self.graph['edges']))
        ledger = [json.loads(line) for line in
                  (extracted / 'handoff/edge_dispositions.jsonl').read_text().splitlines()]
        self.assertEqual({row['edge_id'] for row in ledger}, {row['id'] for row in self.graph['edges']})
        self.assertEqual(len(ledger), len(self.graph['edges']))
        self.assertTrue(all(row['decision'] == 'abstain' and row['confidence'] is None for row in ledger))
        answer = read(extracted / 'runs/question_judge_focus/question.json')
        verify_answer(answer)
        self.assertEqual(answer['source_run'], delivery.RUN_ID)
        self.assertEqual(answer, answer_question(reopened, self.graph['targets'][0]['id'],
                         relations=['interactions'], view='candidates', source_run=delivery.RUN_ID))
        self.assertEqual(answer['answer_sha256'], result['saved_answers']['focus_answer_sha256'])
        instructions = (extracted / 'README_DEMO.md').read_text()
        self.assertIn('?run=' + delivery.RUN_ID + '&question=question_judge_focus', instructions)
        self.assertIn('has not been published or cleared for redistribution', instructions)
        self.assertEqual(delivery.inventory(self.packet), before_packet)
        self.assertEqual(delivery.inventory(self.run), before_run)

    def test_tampered_source_packet_fails_before_runtime_or_output_creation(self):
        path = self.packet / 'edges.jsonl'
        path.write_bytes(path.read_bytes() + b'\n')
        with patch.object(delivery, 'runtime') as runtime:
            with self.assertRaises(ValueError):
                self.prepare(runtime_builder=runtime)
            runtime.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_archive_temp_alias_replays_assay_packet_without_weakening_source_checks(self):
        source, publication, attached, packet = (self.root / name for name in
            ('assay_cohort', 'assay_publication', 'assay_attached', 'assay_packet'))
        save_run(cohort_snapshot(), source)
        make_publication(publication)
        graph = attach_assay(source, publication, attached)
        export_packet(attached, packet)
        before = delivery.inventory(packet)

        # Reproduce a system temporary-root alias on every platform, rather
        # than relying on the host's /var -> /private/var configuration.
        canonical = self.root / 'canonical_temporary_parent'
        canonical.mkdir()
        alias = self.root / 'temporary_parent_alias'
        alias.symlink_to(canonical, target_is_directory=True)
        original_temporary = tempfile.TemporaryDirectory
        returned_names = []

        def aliased_temporary(*args, **kwargs):
            kwargs['dir'] = alias
            temporary = original_temporary(*args, **kwargs)
            returned_names.append(Path(temporary.name))
            self.assertTrue(alias in Path(temporary.name).parents)
            return temporary

        output = self.root / 'assay_delivery'
        with patch.object(delivery.tempfile, 'TemporaryDirectory', side_effect=aliased_temporary), \
                patch.object(delivery, 'load_decisions', wraps=load_decisions) as replay:
            result = delivery.prepare(packet, output, ref='invented-release', runtime_builder=tiny_runtime)
        self.assertEqual(len(returned_names), 2)
        self.assertTrue(all(not name.exists() for name in returned_names))
        self.assertTrue(all(Path(call.args[0]) == Path(call.args[0]).resolve()
                            for call in replay.call_args_list))
        self.assertEqual(result['decisions']['abstain'], len(graph['edges']))
        self.assertEqual(delivery.inventory(packet), before)

        extracted = canonical / 'downloaded'
        with zipfile.ZipFile(output / result['local_data_archive']['file']) as archive:
            archive.extractall(extracted)
        report, retained = load_decisions(extracted / 'handoff')
        reopened = read_run(extracted / 'runs' / delivery.RUN_ID)[2]
        self.assertEqual(report['counts']['abstain'], len(graph['edges']))
        self.assertEqual(reopened['assay_observations'], graph['assay_observations'])
        for key in ('nodes', 'edges', 'assertions'):
            self.assertEqual(retained[key], reopened[key])
        # Resolving an internally created extraction root must not permit a
        # caller-supplied symlink traversal through the actual source reader.
        with self.assertRaisesRegex(ValueError, 'symlink'):
            load_decisions(alias / 'downloaded' / 'handoff')

    def test_existing_or_nested_output_is_refused_without_changing_source(self):
        before = delivery.inventory(self.packet)
        self.out.mkdir()
        for destination in (self.out, self.packet, self.packet / 'nested_output'):
            with self.subTest(destination=destination.name):
                with patch.object(delivery, 'runtime') as runtime:
                    with self.assertRaisesRegex(ValueError, 'new immutable output'):
                        delivery.prepare(self.packet, destination, runtime_builder=runtime)
                    runtime.assert_not_called()
        self.assertEqual(delivery.inventory(self.packet), before)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_source_change_during_delivery_prevents_success_receipt(self):
        original_archive = delivery.archive
        calls = 0

        def mutate_after_archive(folder, destination):
            nonlocal calls
            result = original_archive(folder, destination)
            calls += 1
            if calls == 2:
                path = self.packet / 'edges.jsonl'
                path.write_bytes(path.read_bytes() + b'\n')
            return result

        with patch.object(delivery, 'archive', side_effect=mutate_after_archive):
            with self.assertRaisesRegex(ValueError, 'Original source packet changed'):
                self.prepare()
        self.assertFalse((self.out / 'delivery.json').exists())

    def test_download_tampering_is_rejected_by_existing_offline_verifiers(self):
        result = self.prepare()
        extracted = self.root / 'changed_download'
        with zipfile.ZipFile(self.out / result['local_data_archive']['file']) as archive:
            archive.extractall(extracted)
        retained_path = extracted / 'handoff/retained_graph.json'
        retained_path.write_bytes(retained_path.read_bytes() + b'\n')
        with self.assertRaises(ValueError):
            load_decisions(extracted / 'handoff')
        workspace_path = extracted / 'runs' / delivery.RUN_ID / 'snapshot.json'
        changed = read(workspace_path)
        changed['targets'][0]['name'] = 'Invented changed downloaded source'
        workspace_path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            read_run(workspace_path.parent)

    def test_unsafe_runtime_member_cannot_escape_delivery_directory(self):
        def unsafe_runtime(output, ref):
            output.mkdir(parents=True)
            bundle = output / 'source.tar.gz'
            with tarfile.open(bundle, 'w:gz') as archive:
                member = tarfile.TarInfo('../escaped.py')
                content = b'Invented traversal fixture'
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            return bundle, COMMIT

        with self.assertRaisesRegex(ValueError, 'Unexpected runtime archive member'):
            self.prepare(runtime_builder=unsafe_runtime)
        self.assertFalse((self.out / 'escaped.py').exists())
        self.assertFalse((self.out / 'delivery.json').exists())


if __name__ == '__main__':
    unittest.main()
