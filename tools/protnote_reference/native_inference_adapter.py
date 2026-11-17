"""Draft inference-only interface to unchanged MIT ProtNote classes.

Research staging only: requires native-checkpoint qualification and source parity
before any cohort inference. This module never reads labels from FASTA headers,
never reads reference annotations, trains, or downloads anything.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Any
import hashlib
import json
import pathlib
import re

AA20 = 'ACDEFGHIKLMNPQRSTVWY'
E5_TASK = "Identify the main categories, themes, or topics described in the following Gene Ontology (GO) term, which is used to detail a protein's function"

@dataclass(frozen=True)
class FunctionText:
    go_id: str
    name: str
    definition: str


@dataclass(frozen=True)
class LabelCache:
    ontology_sha256: str
    axis_sha256: str
    go_ids: tuple[str, ...]
    checkpoint_sha256: str
    source_fingerprint: str
    tokenizer_fingerprint: str
    embeddings: Any


def fixed_function_axis(ontology_terms: Sequence[FunctionText]) -> tuple[FunctionText, ...]:
    """An explicitly supplied, dated ontology axis; no target labels accepted."""
    rows = tuple(sorted(ontology_terms, key=lambda r: r.go_id))
    if not rows or len({r.go_id for r in rows}) != len(rows):
        raise ValueError('Require a nonempty axis with unique ontology GO IDs')
    for r in rows:
        if not re.fullmatch(r'GO:\d{7}', r.go_id) or not r.name or not r.definition:
            raise ValueError('Require a GO ID, name and definition for every class')
    return rows


def axis_texts(axis: Sequence[FunctionText]) -> list[str]:
    """Native name/definition order; preserve released E5 instruction."""
    def clean(text: str) -> str:
        # Native download_GO_annotations.calculate_label removes citations/quotes.
        return re.sub(r'\s*\[.*?\]\s*', '', text).strip('"')
    from protnote.utils.data import remove_obsolete_from_string
    return [f'Instruct: {E5_TASK}\nQuery: {remove_obsolete_from_string(description)}'
            for row in axis for description in (row.name, clean(row.definition))]


def axis_sha256(axis: Sequence[FunctionText], ontology_sha256: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{64}', ontology_sha256):
        raise ValueError('Require the independently fixed ontology SHA256')
    content = {'ontology_sha256': ontology_sha256,
               'go_ids': [row.go_id for row in axis], 'texts': axis_texts(axis),
               'pooling': 'mean', 'account_for_sos': True, 'max_tokens': 510}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


class NativeProtNote:
    """Explicit feature axes around the author's unmodified numerical model."""
    def __init__(self, *, checkpoint_path: pathlib.Path,
                 e5_config_path: pathlib.Path, checkpoint_sha256: str, device: str = 'cpu'):
        import torch
        from transformers import AutoModel, XLMRobertaConfig
        from protnote.models.ProtNote import ProtNote
        from protnote.models.protein_encoders import ProteInfer
        import inspect
        self.torch = torch
        if not re.fullmatch(r'[0-9a-f]{64}', checkpoint_sha256):
            raise ValueError('Require verified checkpoint SHA256 from intake receipt')
        digest = hashlib.sha256()
        with checkpoint_path.open('rb') as handle:
            for part in iter(lambda: handle.read(8*1024*1024), b''):
                digest.update(part)
        if digest.hexdigest() != checkpoint_sha256:
            raise ValueError('Checkpoint differs from qualified intake receipt')
        self.checkpoint_sha256 = checkpoint_sha256
        source_files = [pathlib.Path(inspect.getsourcefile(ProtNote)),
                        pathlib.Path(inspect.getsourcefile(ProteInfer)),
                        pathlib.Path(__file__), e5_config_path]
        source_metadata = {'checkpoint_sha256': checkpoint_sha256,
            'official_source_commit': 'b29e17fa308d8c0fc1d9692f705b37dff3a8cf5e',
            'actual_file_hashes': {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in source_files}}
        self.source_fingerprint = hashlib.sha256(json.dumps(source_metadata,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.device = torch.device(device)
        # Construct architecture from local pinned configuration; no hub weights.
        cfg = XLMRobertaConfig.from_json_file(str(e5_config_path))
        if (cfg.hidden_size, cfg.num_hidden_layers, cfg.vocab_size) != (1024, 24, 250002):
            raise ValueError('E5 configuration does not match native architecture')
        label_encoder = AutoModel.from_config(cfg)
        sequence_encoder = ProteInfer(num_labels=32102, input_channels=20,
            output_channels=1100, kernel_size=9, activation=torch.nn.ReLU,
            dilation_base=3, num_resnet_blocks=5, bottleneck_factor=.5)
        self.model = ProtNote(protein_embedding_dim=1100, label_embedding_dim=1024,
            latent_dim=1024, label_embedding_pooling_method='mean',
            inference_descriptions_per_label=2, label_encoder=label_encoder,
            sequence_encoder=sequence_encoder, train_sequence_encoder=False,
            label_encoder_num_trainable_layers=0, sequence_embedding_dropout=0,
            label_embedding_dropout=0, label_embedding_noising_alpha=20,
            output_mlp_hidden_dim_scale_factor=3, output_mlp_num_layers=3,
            output_neuron_bias=None, outout_mlp_add_batchnorm=True,
            residual_connection=False, projection_head_num_layers=4, dropout=0,
            projection_head_hidden_dim_scale_factor=3,
            feature_fusion='concatenation', temperature=.07)
        checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
        state = checkpoint['model_state_dict']
        if all(key.startswith('module.') for key in state):
            state = {key[7:]: value for key, value in state.items()}
        # Includes both encoders. Never silently ignore or initialize missing keys.
        self.model.load_state_dict(state, strict=True)
        del checkpoint, state
        self.model.eval().requires_grad_(False)
        self.model.to(self.device)

    def sequence_features(self, sequence: str):
        """Full sequence, fixed native channels, no labels/IDs/header features."""
        torch = self.torch
        if not sequence or set(sequence) - set(AA20):
            raise ValueError('Empty/noncanonical sequence: no substitution is inferred')
        idx = torch.tensor([AA20.index(aa) for aa in sequence], dtype=torch.long)
        onehots = torch.nn.functional.one_hot(idx, num_classes=20).T.float()[None]
        lengths = torch.tensor([len(sequence)], dtype=torch.long)
        return onehots.to(self.device), lengths.to(self.device)

    def generate_label_cache(self, *, axis: Sequence[FunctionText], ontology_sha256: str,
                             tokenizer_path: pathlib.Path, batch_size: int = 50):
        """Generate only dated function-text vectors, no target/reference input."""
        from transformers import AutoTokenizer
        from protnote.utils.models import generate_label_embeddings_from_text
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
        # Native helper sets encoder.eval and applies its own native autocast.
        axis = fixed_function_axis(axis)
        token_files = ['config.json', 'tokenizer.json', 'tokenizer_config.json',
                       'special_tokens_map.json', 'sentencepiece.bpe.model']
        token_metadata = {name: hashlib.sha256((tokenizer_path/name).read_bytes()).hexdigest()
                          for name in token_files}
        tokenizer_fingerprint = hashlib.sha256(json.dumps(token_metadata,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        try:
            vectors = generate_label_embeddings_from_text(
                label_annotations=axis_texts(axis), label_tokenizer=tokenizer,
                label_encoder=self.model.label_encoder, pooling_method='mean',
                batch_size_limit=batch_size, append_in_cpu=True,
                account_for_sos=True).detach().cpu()
        finally:
            # Native multi-batch embedding helper calls model.train() on exit.
            self.model.eval()
        return LabelCache(ontology_sha256=ontology_sha256,
            axis_sha256=axis_sha256(axis, ontology_sha256),
            go_ids=tuple(row.go_id for row in axis),
            checkpoint_sha256=self.checkpoint_sha256,
            source_fingerprint=self.source_fingerprint,
            tokenizer_fingerprint=tokenizer_fingerprint, embeddings=vectors)

    def predict_sequence(self, *, sequence: str, axis: Sequence[FunctionText],
                         cache: LabelCache, ontology_sha256: str, label_chunk_size: int = 128,
                         reuse_sequence_embeddings: bool = False):
        """Return native probabilities on a fixed axis; no ontology propagation."""
        torch = self.torch
        canonical_axis = fixed_function_axis(axis)
        if tuple(axis) != canonical_axis:
            raise ValueError('Require exact canonical ordered GO axis; no silent reorder')
        axis = canonical_axis
        if (cache.ontology_sha256 != ontology_sha256
            or cache.axis_sha256 != axis_sha256(axis, ontology_sha256)
            or cache.go_ids != tuple(row.go_id for row in axis)
            or cache.checkpoint_sha256 != self.checkpoint_sha256
            or cache.source_fingerprint != self.source_fingerprint
            or not re.fullmatch(r'[0-9a-f]{64}', cache.tokenizer_fingerprint)):
            raise ValueError('Label cache axis/text/ontology/checkpoint identity mismatch')
        label_embeddings = cache.embeddings
        if label_chunk_size < 1 or tuple(label_embeddings.shape) != (2*len(axis), 1024):
            raise ValueError('Require complete ordered name+definition vectors per GO')
        onehots, lengths = self.sequence_features(sequence)
        pieces = []
        with torch.inference_mode():
            # Native forward explicitly supports precomputed sequence embeddings.
            # Scheduling optimization remains off until same-precision parity passes.
            sequence_embeddings = None
            if reuse_sequence_embeddings:
                with torch.cuda.amp.autocast(enabled=self.device.type == 'cuda'):
                    sequence_embeddings = self.model.sequence_encoder.get_embeddings(onehots, lengths)
            for start in range(0, len(axis), label_chunk_size):
                vectors = label_embeddings[2*start:2*(start+label_chunk_size)].to(self.device)
                # Match native Trainer evaluation_step autocast and unchanged forward.
                with torch.cuda.amp.autocast(enabled=self.device.type == 'cuda'):
                    feature_inputs = ({'sequence_embeddings': sequence_embeddings}
                        if reuse_sequence_embeddings else
                        {'sequence_onehots': onehots, 'sequence_lengths': lengths})
                    logits, _ = self.model(**feature_inputs, label_embeddings=vectors,
                        save_embeddings=False)
                pieces.append(torch.sigmoid(logits).detach().cpu())
        scores = torch.cat(pieces, dim=1)[0]
        if scores.numel() != len(axis) or not torch.isfinite(scores).all():
            raise RuntimeError('Missing/nonfinite native forecast')
        return scores
