# Inspect source papers for a supplied question

This optional command-line utility finds candidate PubMed papers and saves an
inspectable handoff. It does not answer the biological question, change the
graph, or accept/prune evidence. It is separate from the hosted app panels.
No BioASQ dataset, reference answers, or `ijson` installation is required.
The [combined assessment](evaluations/COMBINED_CONTEXT_AND_SKILLS_20261114.md)
records the controlled comparisons; the instructions below make no additional
performance claim.

Native search is the recommended starting point: it recovered more known
reference papers than either tested agent condition. The optional model can
return an invalid or empty final result. A separate public example failed
before its first source call; its failure is retained in the
[operator demonstration capsule](evaluations/source_operator_20261114_summary.json).

## 1. Qualify your Mac binary

Run these commands from the repository root with Python 3.10 or newer.
The current qualification command supports **Apple Silicon macOS only**.
It downloads the official
[BioMCP v0.9.3 Mac arm64 release](https://github.com/genomoncology/biomcp/releases/download/v0.9.3/biomcp-darwin-arm64.tar.gz),
checks its archive hash, extracts the executable, and records version/help
checks. It makes no article search or model call.

```sh
python3 -m tools.source_search.prepare qualify \
  --output runs/operator_biomcp_mac_v093

BIOGRAPH_SOURCE_QUAL_SHA256="$(python3 -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("runs/operator_biomcp_mac_v093/qualification.json").read_bytes()).hexdigest())')"
```

Use a new qualification directory if that name already exists. The pinned
archive is 16,075,492 bytes, SHA256
`e637062c18c6692f3ec49c5847e69b29f6feee7f7909345970bd504d72174994`.
The previously qualified executable was 33,699,984 bytes, SHA256
`54f66769d9193c569d1b65756ad766eafd1a2c5e92d08f8c855cc8964e9a7145`.
Its source commit is
[`5641de7d7b79b53872f8599dbb4dba22e611dcaf`](https://github.com/genomoncology/biomcp/tree/5641de7d7b79b53872f8599dbb4dba22e611dcaf).

The next command requires the **qualification file's SHA256**, calculated above,
not the archive hash, executable hash, or JSON `content_sha256`. Each receipt
contains its machine's absolute executable path. Another Mac operator must run
the qualification command locally rather than reuse this project's saved Mac
receipt blindly. Linux/AWS and Intel Mac binaries are **not qualified by this
setup command**; do not substitute one while retaining the Mac receipt.

## 2. Start with native search

```sh
python3 -m tools.source_search.query \
  --question 'Pharos TCRD' \
  --qualification runs/operator_biomcp_mac_v093/qualification.json \
  --qualification-sha256 "$BIOGRAPH_SOURCE_QUAL_SHA256" \
  --mode native \
  --cache runs/source_paper_operator_cache \
  --output runs/source_paper_native_01
```

Replace the example with your public research question. Native mode is the
default and uses one PubMed search, up to ten candidates, **zero model/tokenizer
calls**, no paid API, and no Brev instance. BioMCP receives the query through its
published PubMed-only search surface; other source enrichment is disabled.

Choose a **new output directory for every run**. A cache directory can be reused;
its saved responses are immutable and bound to the query, binary and helper
hashes. A cache hit reuses the captured response rather than performing a fresh
search. Use a new cache directory when a fresh retrieval is intended.

## 3. Read the handoff

Open `runs/source_paper_native_01/report.html` in your ordinary browser. The
report shows:

- Search candidates with canonical PubMed links and saved source records.
- Source-query status, incomplete/unavailable results, and any recorded
  retraction, publication or correction flags. “Not recorded” and empty values
  do not establish a clean publication status.
- Any completed final agent selection, separately from candidates already
  captured when an agent stops. An empty selection does not establish that
  relevant evidence is absent.
- The exact article opened, if any, and its identity/abstract availability.
  A final handoff can include candidates whose abstracts were not opened.
- Separate model/tokenizer and source-tool/cache counts. These are not exact
  upstream HTTP counts or dollar charges.

`operator_receipt.json` seals the settings, code/source pins, costs and saved
file hashes. `question.json` preserves the supplied question;
`workflow/result.json` preserves the workflow result; `workflow/tool_result*.json`
preserves tool observations. The shared cache retains the complete native
captures. Exact values remain in JSON while the HTML presents readable labels.

**Pharos/evidence reuse is unassessed.** A found paper is candidate source
context, not independent new graph evidence. Ranking, a valid PMID, or reading
an abstract does not establish claim support, biological truth, or absence of
source duplication. Nothing is automatically ingested or accepted.

## 4. Optional existing-Nano agent

After starting the already qualified Brev model service and its existing
loopback forward yourself, run:

```sh
python3 -m tools.source_search.query \
  --question 'Pharos TCRD' \
  --qualification runs/operator_biomcp_mac_v093/qualification.json \
  --qualification-sha256 "$BIOGRAPH_SOURCE_QUAL_SHA256" \
  --mode agent --procedure base \
  --endpoint http://127.0.0.1:8011/v1/chat/completions \
  --cache runs/source_paper_operator_cache \
  --output runs/source_paper_agent_01
```

This utility does not start compute or install/replace a model. It targets the
existing `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` service, whose runtime qualification
is separate; the model name alone does not prove its revision. The endpoint
must be credential-free loopback. Brev compute has its normal cost.

Agent limits are four generation calls, at most 1,200 output tokens each,
two searches, one exact-PMID abstract get, and ten unique final PMIDs selected
from returned candidates. A conservative 8,192-token context cap is checked
with the existing server's tokenizer before generation. A rejected duplicate
search consumes a decision and returns feedback without another source call;
the fourth decision must finish. Other failures remain explicit, with captured
papers retained rather than presented as a completed answer.

Questions must be nonblank, at most 5,000 characters, and contain no NUL.
Each search query is limited to 2,000 characters; native mode passes the entire
question as its query, so use at most 2,000 characters there. Unsupported input
is not silently shortened or broadened.

### Troubleshoot a verified Mac system-proxy refusal

An abstract fetch can fail even when native search works: Python's default
`urllib` opener can discover macOS system proxies when proxy environment
variables are absent. One paired check in this project reproduced a default
connection refusal and a successful direct HTTPS fetch for the same record.
An `URLError` alone does not identify that cause. See Python 3.14's official
[`getproxies`](https://docs.python.org/3.14/library/urllib.request.html#urllib.request.getproxies)
and [`ProxyHandler`](https://docs.python.org/3.14/library/urllib.request.html#urllib.request.ProxyHandler)
documentation.

For that verified local configuration problem, when direct internet access is
permitted, apply the documented proxy setting to **one new process**:

```sh
env NO_PROXY='*' no_proxy='*' python3 -m tools.source_search.query \
  --question 'Pharos TCRD' \
  --qualification runs/operator_biomcp_mac_v093/qualification.json \
  --qualification-sha256 "$BIOGRAPH_SOURCE_QUAL_SHA256" \
  --mode agent --procedure base \
  --endpoint http://127.0.0.1:8011/v1/chat/completions \
  --cache runs/source_paper_direct_transport_cache_01 \
  --output runs/source_paper_direct_transport_01
```

This uses the optional existing model described above; it does not start Brev.
Use a **new `--cache` as well as a new `--output`**: unavailable responses are
saved immutably, so reusing their cache would repeat the saved failure without
testing the corrected transport. Keep the old cache and report for comparison.
The process setting leaves global proxy settings, TLS certificate verification
and project code unchanged. It is not a remedy for access-policy or security
restrictions, and successful retrieval still requires inspecting the new
report's source status.

`--procedure reviewed` explicitly adds the attributed evidence-search checklist;
`base` is the default. Neither is assumed superior. The checklist adapts
[BioMCP's MIT skill](https://github.com/genomoncology/biomcp/blob/5641de7d7b79b53872f8599dbb4dba22e611dcaf/skills/SKILL.md)
and the selected MIT-labelled K-Dense
[ontology-term-resolution](https://github.com/K-Dense-AI/scientific-agent-skills/blob/526ebce143bc326f44471554e33d66a19c840360/skills/ontology-term-resolution/SKILL.md),
[scientific-critical-thinking](https://github.com/K-Dense-AI/scientific-agent-skills/blob/526ebce143bc326f44471554e33d66a19c840360/skills/scientific-critical-thinking/SKILL.md)
and [peer-review](https://github.com/K-Dense-AI/scientific-agent-skills/blob/526ebce143bc326f44471554e33d66a19c840360/skills/peer-review/SKILL.md)
procedures. Exact attributions/hashes are in
[`policy.py`](../tools/source_search/policy.py) and the operator receipt;
upstream provider/data rights remain separate. Installing a skill in Codex does
not wire it into the NVIDIA agent: this utility supplies its reviewed
instructions explicitly.
