## Exploratory secondary uncertainty

**Post-hoc and not multiplicity adjusted.** All six original fill point values
were already seen before these secondary intervals were specified. Both MFO
and CCO, both existing cohorts and both readouts are retained regardless of
direction. The original failed BPO adoption rule and retained LocalPlus
profile remain unchanged; these intervals do not authorize a DeepGO consumer.

| Cohort | Aspect | Readout | Paired 95% interval | Bootstrap mean difference |
| --- | --- | --- | --- | ---: |
| Original PK | MFO | ordinary | [0.023643, 0.079023] | 0.050267 |
| Original PK | MFO | IA_weighted | [0.017106, 0.066798] | 0.040737 |
| Original PK | CCO | ordinary | [-0.022818, 0.025372] | 0.001633 |
| Original PK | CCO | IA_weighted | [-0.037464, 0.005884] | -0.016344 |
| Additional PK | MFO | ordinary | [0.016057, 0.053031] | 0.034823 |
| Additional PK | MFO | IA_weighted | [0.033145, 0.056185] | 0.044687 |
| Additional PK | CCO | ordinary | [-0.002064, 0.025082] | 0.011220 |
| Additional PK | CCO | IA_weighted | [-0.005211, 0.019006] | 0.006661 |

Differences are DeepGO minus matched full strict-source LocalPlus. Each
cohort/aspect uses the same 2,000 paired protein draws (seed 20261113),
unchanged native fill confusion counts and fixed Fmax threshold grid.
Both methods passed saved native point/count agreement. Protein/source
dependence, incomplete annotations and reused-label exposure remain;
these are conditional descriptive intervals rather than independent
biological confirmation or calibrated confidence.

Source aggregate FILE SHA-256: `6a36c63f4eeb6a5aae803f09df2c588c58956f309ababd82a3f84e582f07aec9`.
Post-hoc source-freeze FILE SHA-256: `52a025d396ed7aeca7dff82ca593a0f39d74da663b4a04b6320bfeed2df39ed1`.
