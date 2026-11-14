This optional research package retains BioGraph Steward's MIT license for its
original adapter/controller code. Its short procedure in `policy.py` adapts
published workflow ideas from the following separately attributed sources:

- BioMCP v0.9.3, `skills/SKILL.md`, commit
  `5641de7d7b79b53872f8599dbb4dba22e611dcaf`.
  Copyright (c) 2025 Ian Maurer. The pinned upstream notice is preserved in
  `LICENSE.BioMCP.MIT.txt`.
- Scientific Agent Skills v2.72.0, `ontology-term-resolution`,
  `scientific-critical-thinking` and `peer-review` instruction files, commit
  `526ebce143bc326f44471554e33d66a19c840360`.
  Copyright (c) 2025 K-Dense Inc. The pinned upstream notice is preserved in
  `LICENSE.K-Dense.MIT.txt`. Exact source-file hashes and adaptation roles are
  recorded in `policy.py`.

The full external skills and native executable are task-local ignored artifacts;
they are not globally installed Codex skills or core app dependencies. No
upstream endorsement or published accuracy gain for this adaptation is implied.

BioASQ11 reference data has its own CC-BY-2.5 license at
https://doi.org/10.5281/zenodo.7655130. Cite Krithara et al.,
https://doi.org/10.1038/s41597-023-02068-4, and preserve attribution when reusing
its data. Software licenses do not replace PubMed/publisher or article-specific
rights in retrieved text. Raw reference cases and source text are not included
in the aggregate assessment by default.
