# SPDX-License-Identifier: GPL-3.0-only
"""Boolean GOA sidecars for the existing native variable-width context input.

This is an I/O adapter, not a grouping/ontology/loss implementation. The source
qualified producer owns each channel's evidence/relationship/count semantics.
Only a fetched row is expanded to native float32 alongside the original eight
parent features. Full protein×GO×context float32 caches are not constructed.
"""
import json
from pathlib import Path

from .native_stacker import context_axis, need
from .training import CachedNativeDataset, require_pinned, sha


CONTEXT_FORMAT = 'biograph-steward.contextual-boolean-features.v1'


def read_boolean_context(path, pins, base_manifest):
    """Verify literal axes/order and a separately pinned boolean memory map."""
    import numpy as np

    require_pinned(path, pins)
    meta = json.loads(Path(path).read_text())
    need(meta.get('format') == CONTEXT_FORMAT, 'unqualified boolean context artifact format.')
    channels = context_axis(meta['channels'])
    need(meta['proteins'] == base_manifest['proteins'] and meta['terms'] == base_manifest['terms'],
         'context and parent protein/GO identity axes differ; no implicit reindexing.')
    need(meta.get('fresh_final_reference_opened') is False, 'context producer must retain the final-reference boundary.')
    require_pinned(meta['context_file'], pins)
    need(sha(meta['context_file']) == meta['context_sha256'], 'boolean context content differs from its declaration.')
    values = np.load(meta['context_file'], mmap_mode='r', allow_pickle=False)
    need(values.dtype == np.bool_ and values.shape ==
         (len(meta['proteins']), len(channels), len(meta['terms'])),
         'context cache must be bool Nprotein×NdeclaredChannels×NmodelTerms.')
    return meta, values


class BooleanContextDataset(CachedNativeDataset):
    """Replace only the default GOA channel using native ordered bool inputs."""
    def __init__(self, manifest, features, graph, context_manifest, context_values,
                 targets=None, *, row_indices=None):
        import numpy as np

        super().__init__(manifest, features, graph, targets, row_indices=row_indices)
        need(context_manifest['proteins'] == manifest['proteins']
             and context_manifest['terms'] == manifest['terms'], 'boolean-context identity axes differ from parent cache.')
        self._biograph_context_channels = context_axis(context_manifest['channels'])
        need(context_values.dtype == np.bool_ and context_values.shape ==
             (len(manifest['proteins']), len(self._biograph_context_channels), len(manifest['terms'])),
             'complete boolean context cache on all literal axes required.')
        self.context = context_values

    def __getitem__(self, index):
        import numpy as np
        import torch

        batch = super().__getitem__(index)
        context = torch.from_numpy(np.array(self.context[self.rows[index]], dtype=np.float32, copy=True))
        batch['x'] = torch.cat((batch['x'][:8], context), dim=0)
        return batch
