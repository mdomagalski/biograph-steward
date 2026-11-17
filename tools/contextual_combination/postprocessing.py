"""Fixed published ProtBoost soft GO closure, without its submission data merge.

The exact author traversal/function bodies are isolated from pinned source.
A NumPy implementation of its simple MAX/MIN CUDA kernel permits CPU use in
both isolated runtimes. No annotation file, TTA, top-k or score truncation is
run. This is a full-precision backend/presentation adaptation, not a new graph
algorithm. The fixed 0.7 and 0.5 come from the author's executed notebook recipe,
not the step CLI's different default0.1 or a search on this project's results.
"""
import hashlib
from pathlib import Path

from .native_stacker import _symbols, need, sequence_edge_graph


POSTPROCESS_SOURCE_PINS = {
    'LICENSE': '352a4208310cd9e8be157e00979dd06f375fbdbf384e4b691a2af1fcc9079600',
    'protlib/metric.py': 'ab2deadf5041e0b3034ae0876c85941dff5343e3a7895798d522253789678f63',
    'protlib/scripts/postproc/step.py': 'c15e366e576628c086fbebc4199cecd34e1f5d02f5c0dac6d1af1b61cd69b2ce',
    'protlib/scripts/postproc/make_submission.py': '036bf14c532ae1ca637b45c5413591ecac23356f0dcaeaf93a2c06bf15c7dce7',
    'CAFA5PIpeline.ipynb': 'dbf69b93be22a8d55e42db3d488acc4b21c00cd917c8a1a152046101a1abe657',
}
SOFT_RATE = .7
MAX_MIN_RATE = .5


class _NumpyKernelBackend:
    """Only the exact pinned author MAX/MIN kernel signatures, no CUDA calls."""
    def __init__(self, np):
        self.np, self.int64 = np, np.int64
        self.arange, self.asarray = np.arange, np.asarray
        self.kernel_bodies = {}

    def ElementwiseKernel(self, inputs, outputs, operation, name):
        compact = lambda value: ''.join(value.split())
        need(compact(inputs) == 'int64i_,rawint64j_,int64col,int64l,int64lx'
             and compact(outputs) == 'rawfloat32arr', 'unexpected upstream kernel signature.')
        need(name in ('propagate_max_kernel', 'propagate_min_kernel'), 'unexpected upstream kernel name.')
        direction = name.split('_')[1]
        expected = ('intk;for(k=0;k<l;k++){arr[i_*lx+col]=' + direction
                    + '(arr[i_*lx+col],arr[i_*lx+j_[k]]);}')
        need(compact(operation) == expected, 'upstream MAX/MIN kernel body differs.')
        self.kernel_bodies[name] = hashlib.sha256(operation.encode()).hexdigest()
        function = self.np.maximum if direction == 'max' else self.np.minimum
        def execute(rows, adjacent, column, length, width, flat):
            matrix = flat.reshape((-1, width))
            for adjacent_index in adjacent[:length]:
                matrix[rows, column] = function(matrix[rows, column], matrix[rows, adjacent_index])
        return execute


def load_postprocessor(author_root):
    import numpy as np
    import pandas as pd

    root = Path(author_root)
    for name, pin in POSTPROCESS_SOURCE_PINS.items():
        need((root / name).is_file() and hashlib.sha256((root / name).read_bytes()).hexdigest() == pin,
             'changed published postprocessing source: ' + name)
    backend = _NumpyKernelBackend(np)
    native = {'pd': pd, 'cp': backend}
    ast_pins = _symbols(root / 'protlib/metric.py', ('get_depths',), native)
    ast_pins.update(_symbols(root / 'protlib/scripts/postproc/step.py',
                             ('get_kernel', 'propagate_max', 'propagate_min'), native))
    native['prop_max_kernel'] = native['get_kernel']('max')
    native['prop_min_kernel'] = native['get_kernel']('min')
    receipt = {'source_sha256': dict(POSTPROCESS_SOURCE_PINS), 'selected_symbol_ast_sha256': ast_pins,
               'kernel_body_sha256': dict(backend.kernel_bodies),
               'soft_rate': SOFT_RATE, 'max_min_rate': MAX_MIN_RATE,
               'source': 'author notebook section4.3 uses --lr0.7 for each direction and --max-rate0.5',
               'backend_adaptation': 'NumPy implementation of exact source MAX/MIN elementwise kernel body',
               'graph_container_adaptation': 'same native integer edge sets materialized as sorted lists; no edge or identity changes',
               'score_presentation_adaptation': 'keep full float32 values; no string truncation/top500/annotation merge',
               'annotation_or_reference_files_read': False,
               'guarantees_strict_parent_ge_child': False}
    return native, receipt


def published_soft_closure(author_root, graph, terms, values):
    """Independent raw→MAX and raw→MIN closure; soft mix then equal average.

    This soft operation can reduce a hierarchy violation but does not guarantee
    parent>=child. Never describe it as strict hierarchy enforcement. Both
    closure directions start from separate copies of the identical raw matrix.
    """
    import numpy as np

    terms, values = tuple(terms), np.asarray(values)
    need(terms == tuple(node['id'] for node in graph.terms_list)
         and len(terms) == graph.idxs and len(set(terms)) == len(terms),
         'postprocessing requires the fixed literal model GO axis.')
    need(values.ndim == 2 and values.shape[1] == len(terms) and values.dtype == np.float32
         and np.isfinite(values).all() and (values >= 0).all() and (values <= 1).all(),
         'native postprocessing requires complete finite float32 model probabilities in [0,1].')
    native, receipt = load_postprocessor(author_root)
    # The project's pinned CAFA Graph exposes child sets; the author
    # ProtBoost Graph exposes lists. NumPy/CuPy cannot directly cast a set to
    # an integer vector. MAX/MIN are order-independent on finite values, so
    # materialize the same integer relationships without mutating the graph.
    view = sequence_edge_graph(graph)
    high, low = values.copy(order='C'), values.copy(order='C')
    native['propagate_max'](high, view)
    native['propagate_min'](low, view)
    high = high * SOFT_RATE + values * (1 - SOFT_RATE)
    low = low * SOFT_RATE + values * (1 - SOFT_RATE)
    result = high * MAX_MIN_RATE + low * (1 - MAX_MIN_RATE)
    need(result.dtype == np.float32 and np.isfinite(result).all()
         and (result >= 0).all() and (result <= 1).all(), 'invalid published soft-closure output.')
    return result, receipt
