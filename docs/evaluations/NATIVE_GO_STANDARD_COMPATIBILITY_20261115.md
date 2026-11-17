# Native GO export compatibility correction

The native GO question reader gained an explicit source-policy argument. Its
existing standards consumer still called the former signature, causing a
`TypeError` whenever an otherwise admissible native row reached source replay.
This was our integration regression, reproduced by all five existing native-GO
projection tests. It was not an upstream KGX/Biolink problem.

The consumer now passes the existing strict experimental `goa_source.POLICY`
explicitly. The mapping contract, registered assigning sources, source-profile
gates, ontology, predicates, native sidecar and complete ledgers remain the
same. This correction does not broaden the KGX profile to all native-location
evidence codes or STRING physical associations.

A new invented TAS-record case verifies that nonexperimental source content is
preserved unchanged in the native sidecar and exclusion ledger, while remaining
outside the strict standard projection. The original fixture/source graph is
unchanged by projection.

```sh
python3 -B -m unittest discover -s tests -p 'test_standard*.py' -v
```

Result: **26 passed; four optional upstream-validator tests skipped** because
the active interpreter lacks their pinned environment. The six native-GO tests
pass. Core projection/export/replay tests use their declared fixture and mocked
validator scope; they do not establish a new real-graph KGX validation result.
No source retrieval, package installation, graph edit or deployment was made
by this correction.
