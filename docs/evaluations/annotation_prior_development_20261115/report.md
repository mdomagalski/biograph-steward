# Annotation-prior development follow-up

**DEVELOPMENT — reference already consumed; no independent confirmation.**

One fixed published operation combines the previously selected stacker with the complete legal T0 nonexperimental annotation prior. This report preserves all 18 cells, every original method and every saved contrast, including losses. The original frozen study and its success gates remain unchanged.

## PK overview

These are descriptive readouts from the existing PK endpoint, not newly selected endpoints or new success gates. Every NK/LK readout remains in the complete tables below.

| View | Aspect | Original selected | Selected + prior | Original prior | Matched prior 0.99 | Prior parity |
|---|---|---|---|---|---|---|
| native | Molecular function | 0.245247 | 0.258886 | 0.265878 | 0.265878 | passed |
| native | Biological process | 0.073431 | 0.046331 | 0.025476 | 0.025476 | passed |
| native | Cellular component | 0.260227 | 0.276155 | 0.321676 | 0.321676 | passed |
| fixed_T0 | Molecular function | 0.299478 | 0.309252 | 0.311316 | 0.311316 | passed |
| fixed_T0 | Biological process | 0.210093 | 0.190092 | 0.146169 | 0.146169 | passed |
| fixed_T0 | Cellular component | 0.267299 | 0.286030 | 0.335678 | 0.335678 | passed |

Fmax is optimized over the unchanged .001–.999 evaluator grid; 0.99 is an author-defined annotation score, not calibrated confidence. Intervals use the same 2,000 paired whole-protein draws as the original study and remain conditional, unadjusted development descriptions. Compare methods within each view; the two views have different reference populations. No model, threshold or new success gate is selected here.

## All 18 cells

### native · PK · Molecular function

Full native/bootstrap protein frame: 324; proteins with residual positive labels: 229. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.109872 | 324 | 229 |
| DeepGO-SE — sequence model | 0.178694 | 324 | 229 |
| LocalPlus — same soft processing | 0.109872 | 324 | 229 |
| DeepGO-SE — same soft processing | 0.177062 | 324 | 229 |
| Fixed 50/50 combination | 0.182346 | 324 | 229 |
| Development-selected global weight | 0.182346 | 324 | 229 |
| LocalPlus — historical model axis | 0.109872 | 324 | 229 |
| DeepGO-SE — historical model axis | 0.178694 | 324 | 229 |
| Current nonexperimental annotations | 0.265878 | 324 | 229 |
| Context stacker — zero-layer MLP | 0.245247 | 324 | 229 |
| Context stacker — eight-layer GCN | 0.230818 | 324 | 229 |
| LocalPlus — matched training-label update | 0.114583 | 324 | 229 |
| Updated LocalPlus — same soft processing | 0.114583 | 324 | 229 |
| Training-label frequency only | 0.067828 | 324 | 229 |
| LocalPlus — complete current-T0 curated seeds | 0.125798 | 324 | 229 |
| Development-selected context stacker | 0.245247 | 324 | 229 |
| Selected stacker + legal T0 annotation prior | 0.258886 | 324 | 229 |
| Matched annotation-only prior at author Float32(0.99) | 0.265878 | 324 | 229 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.149014 | [+0.101277, +0.197722] |
| DeepGO-SE — sequence model | +0.080192 | [+0.043955, +0.112621] |
| LocalPlus — same soft processing | +0.149014 | [+0.101277, +0.197722] |
| DeepGO-SE — same soft processing | +0.081824 | [+0.044262, +0.114216] |
| Fixed 50/50 combination | +0.076540 | [+0.043772, +0.106358] |
| Development-selected global weight | +0.076540 | [+0.043772, +0.106358] |
| LocalPlus — historical model axis | +0.149014 | [+0.101277, +0.197722] |
| DeepGO-SE — historical model axis | +0.080192 | [+0.043955, +0.112621] |
| Current nonexperimental annotations | -0.006992 | [-0.031923, +0.022061] |
| Context stacker — zero-layer MLP | +0.013639 | [-0.005137, +0.023485] |
| Context stacker — eight-layer GCN | +0.028068 | [+0.000990, +0.043342] |
| LocalPlus — matched training-label update | +0.144303 | [+0.097212, +0.193664] |
| Updated LocalPlus — same soft processing | +0.144303 | [+0.097212, +0.193664] |
| Training-label frequency only | +0.191058 | [+0.142854, +0.241240] |
| LocalPlus — complete current-T0 curated seeds | +0.133088 | [+0.083919, +0.182757] |
| Development-selected context stacker | +0.013639 | [-0.005137, +0.023485] |
| Matched annotation-only prior at author Float32(0.99) | -0.006992 | [-0.031923, +0.022061] |

### native · PK · Biological process

Full native/bootstrap protein frame: 1954; proteins with residual positive labels: 322. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.054732 | 1954 | 322 |
| DeepGO-SE — sequence model | 0.036422 | 1954 | 322 |
| LocalPlus — same soft processing | 0.054732 | 1954 | 322 |
| DeepGO-SE — same soft processing | 0.037041 | 1954 | 322 |
| Fixed 50/50 combination | 0.048155 | 1954 | 322 |
| Development-selected global weight | 0.056100 | 1954 | 322 |
| LocalPlus — historical model axis | 0.054732 | 1954 | 322 |
| DeepGO-SE — historical model axis | 0.036422 | 1954 | 322 |
| Current nonexperimental annotations | 0.025476 | 1954 | 322 |
| Context stacker — zero-layer MLP | 0.061746 | 1954 | 322 |
| Context stacker — eight-layer GCN | 0.059725 | 1954 | 322 |
| Context GCN — evidence/relation features | 0.073431 | 1954 | 322 |
| LocalPlus — matched training-label update | 0.055296 | 1954 | 322 |
| Updated LocalPlus — same soft processing | 0.055296 | 1954 | 322 |
| Training-label frequency only | 0.032584 | 1954 | 322 |
| LocalPlus — complete current-T0 curated seeds | 0.058838 | 1954 | 322 |
| Development-selected context stacker | 0.073431 | 1954 | 322 |
| Selected stacker + legal T0 annotation prior | 0.046331 | 1954 | 322 |
| Matched annotation-only prior at author Float32(0.99) | 0.025476 | 1954 | 322 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | -0.008401 | [-0.023249, +0.002848] |
| DeepGO-SE — sequence model | +0.009909 | [+0.002209, +0.018947] |
| LocalPlus — same soft processing | -0.008401 | [-0.023249, +0.002848] |
| DeepGO-SE — same soft processing | +0.009290 | [+0.001312, +0.018578] |
| Fixed 50/50 combination | -0.001824 | [-0.013267, +0.009063] |
| Development-selected global weight | -0.009769 | [-0.023283, +0.000832] |
| LocalPlus — historical model axis | -0.008401 | [-0.023249, +0.002848] |
| DeepGO-SE — historical model axis | +0.009909 | [+0.002209, +0.018947] |
| Current nonexperimental annotations | +0.020855 | [+0.015272, +0.028719] |
| Context stacker — zero-layer MLP | -0.015415 | [-0.024196, -0.007681] |
| Context stacker — eight-layer GCN | -0.013394 | [-0.024169, -0.006203] |
| Context GCN — evidence/relation features | -0.027100 | [-0.038573, -0.018869] |
| LocalPlus — matched training-label update | -0.008965 | [-0.023516, +0.001779] |
| Updated LocalPlus — same soft processing | -0.008965 | [-0.023516, +0.001779] |
| Training-label frequency only | +0.013747 | [+0.002532, +0.025985] |
| LocalPlus — complete current-T0 curated seeds | -0.012507 | [-0.028076, -0.000989] |
| Development-selected context stacker | -0.027100 | [-0.038573, -0.018869] |
| Matched annotation-only prior at author Float32(0.99) | +0.020855 | [+0.015272, +0.028719] |

### native · PK · Cellular component

Full native/bootstrap protein frame: 1296; proteins with residual positive labels: 1230. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.194680 | 1296 | 1230 |
| DeepGO-SE — sequence model | 0.173657 | 1296 | 1230 |
| LocalPlus — same soft processing | 0.194680 | 1296 | 1230 |
| DeepGO-SE — same soft processing | 0.175835 | 1296 | 1230 |
| Fixed 50/50 combination | 0.201061 | 1296 | 1230 |
| Development-selected global weight | 0.201061 | 1296 | 1230 |
| LocalPlus — historical model axis | 0.194680 | 1296 | 1230 |
| DeepGO-SE — historical model axis | 0.173657 | 1296 | 1230 |
| Current nonexperimental annotations | 0.321676 | 1296 | 1230 |
| Context stacker — zero-layer MLP | 0.216454 | 1296 | 1230 |
| Context stacker — eight-layer GCN | 0.260227 | 1296 | 1230 |
| LocalPlus — matched training-label update | 0.193807 | 1296 | 1230 |
| Updated LocalPlus — same soft processing | 0.193807 | 1296 | 1230 |
| Training-label frequency only | 0.106220 | 1296 | 1230 |
| LocalPlus — complete current-T0 curated seeds | 0.167363 | 1296 | 1230 |
| Development-selected context stacker | 0.260227 | 1296 | 1230 |
| Selected stacker + legal T0 annotation prior | 0.276155 | 1296 | 1230 |
| Matched annotation-only prior at author Float32(0.99) | 0.321676 | 1296 | 1230 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.081475 | [+0.062504, +0.098176] |
| DeepGO-SE — sequence model | +0.102498 | [+0.085064, +0.118843] |
| LocalPlus — same soft processing | +0.081475 | [+0.062504, +0.098176] |
| DeepGO-SE — same soft processing | +0.100320 | [+0.082320, +0.116550] |
| Fixed 50/50 combination | +0.075094 | [+0.058603, +0.090980] |
| Development-selected global weight | +0.075094 | [+0.058603, +0.090980] |
| LocalPlus — historical model axis | +0.081475 | [+0.062504, +0.098176] |
| DeepGO-SE — historical model axis | +0.102498 | [+0.085064, +0.118843] |
| Current nonexperimental annotations | -0.045521 | [-0.058301, -0.031453] |
| Context stacker — zero-layer MLP | +0.059701 | [+0.048992, +0.070271] |
| Context stacker — eight-layer GCN | +0.015928 | [+0.009979, +0.021579] |
| LocalPlus — matched training-label update | +0.082348 | [+0.063360, +0.099297] |
| Updated LocalPlus — same soft processing | +0.082348 | [+0.063360, +0.099297] |
| Training-label frequency only | +0.169935 | [+0.151175, +0.188701] |
| LocalPlus — complete current-T0 curated seeds | +0.108792 | [+0.090201, +0.125454] |
| Development-selected context stacker | +0.015928 | [+0.009979, +0.021579] |
| Matched annotation-only prior at author Float32(0.99) | -0.045521 | [-0.058301, -0.031453] |

### native · NK · Molecular function

Full native/bootstrap protein frame: 7; proteins with residual positive labels: 7. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.210526 | 7 | 7 |
| DeepGO-SE — sequence model | 0.405229 | 7 | 7 |
| LocalPlus — same soft processing | 0.210526 | 7 | 7 |
| DeepGO-SE — same soft processing | 0.400000 | 7 | 7 |
| Fixed 50/50 combination | 0.389610 | 7 | 7 |
| Development-selected global weight | 0.389610 | 7 | 7 |
| LocalPlus — historical model axis | 0.210526 | 7 | 7 |
| DeepGO-SE — historical model axis | 0.405229 | 7 | 7 |
| Current nonexperimental annotations | 0.433333 | 7 | 7 |
| Context stacker — zero-layer MLP | 0.387597 | 7 | 7 |
| Context stacker — eight-layer GCN | 0.396396 | 7 | 7 |
| LocalPlus — matched training-label update | 0.210526 | 7 | 7 |
| Updated LocalPlus — same soft processing | 0.210526 | 7 | 7 |
| Training-label frequency only | 0.187919 | 7 | 7 |
| LocalPlus — complete current-T0 curated seeds | 0.237037 | 7 | 7 |
| Development-selected context stacker | 0.387597 | 7 | 7 |
| Selected stacker + legal T0 annotation prior | 0.396825 | 7 | 7 |
| Matched annotation-only prior at author Float32(0.99) | 0.433333 | 7 | 7 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — sequence model | -0.008403 | [-0.137480, +0.216477] |
| LocalPlus — same soft processing | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — same soft processing | -0.003175 | [-0.146285, +0.218288] |
| Fixed 50/50 combination | +0.007215 | [-0.066849, +0.130087] |
| Development-selected global weight | +0.007215 | [-0.066849, +0.130087] |
| LocalPlus — historical model axis | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — historical model axis | -0.008403 | [-0.137480, +0.216477] |
| Current nonexperimental annotations | -0.036508 | [-0.145736, +0.111712] |
| Context stacker — zero-layer MLP | +0.009228 | [-0.004299, +0.032293] |
| Context stacker — eight-layer GCN | +0.000429 | [-0.159879, +0.120884] |
| LocalPlus — matched training-label update | +0.186299 | [-0.021289, +0.411064] |
| Updated LocalPlus — same soft processing | +0.186299 | [-0.021289, +0.411064] |
| Training-label frequency only | +0.208906 | [+0.034264, +0.436431] |
| LocalPlus — complete current-T0 curated seeds | +0.159788 | [-0.044920, +0.411770] |
| Development-selected context stacker | +0.009228 | [-0.004299, +0.032293] |
| Matched annotation-only prior at author Float32(0.99) | -0.036508 | [-0.145736, +0.111712] |

### native · NK · Biological process

Full native/bootstrap protein frame: 8; proteins with residual positive labels: 8. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.213650 | 8 | 8 |
| DeepGO-SE — sequence model | 0.299401 | 8 | 8 |
| LocalPlus — same soft processing | 0.213650 | 8 | 8 |
| DeepGO-SE — same soft processing | 0.301370 | 8 | 8 |
| Fixed 50/50 combination | 0.308540 | 8 | 8 |
| Development-selected global weight | 0.262887 | 8 | 8 |
| LocalPlus — historical model axis | 0.213650 | 8 | 8 |
| DeepGO-SE — historical model axis | 0.299401 | 8 | 8 |
| Current nonexperimental annotations | 0.221344 | 8 | 8 |
| Context stacker — zero-layer MLP | 0.316151 | 8 | 8 |
| Context stacker — eight-layer GCN | 0.282958 | 8 | 8 |
| Context GCN — evidence/relation features | 0.310469 | 8 | 8 |
| LocalPlus — matched training-label update | 0.225705 | 8 | 8 |
| Updated LocalPlus — same soft processing | 0.225705 | 8 | 8 |
| Training-label frequency only | 0.218045 | 8 | 8 |
| LocalPlus — complete current-T0 curated seeds | 0.237069 | 8 | 8 |
| Development-selected context stacker | 0.310469 | 8 | 8 |
| Selected stacker + legal T0 annotation prior | 0.314286 | 8 | 8 |
| Matched annotation-only prior at author Float32(0.99) | 0.221344 | 8 | 8 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.100636 | [-0.019158, +0.169912] |
| DeepGO-SE — sequence model | +0.014885 | [-0.121310, +0.103389] |
| LocalPlus — same soft processing | +0.100636 | [-0.019158, +0.169912] |
| DeepGO-SE — same soft processing | +0.012916 | [-0.118354, +0.095854] |
| Fixed 50/50 combination | +0.005746 | [-0.116716, +0.077998] |
| Development-selected global weight | +0.051399 | [-0.076416, +0.123037] |
| LocalPlus — historical model axis | +0.100636 | [-0.019158, +0.169912] |
| DeepGO-SE — historical model axis | +0.014885 | [-0.121310, +0.103389] |
| Current nonexperimental annotations | +0.092942 | [+0.020858, +0.263295] |
| Context stacker — zero-layer MLP | -0.001865 | [-0.024024, +0.033907] |
| Context stacker — eight-layer GCN | +0.031328 | [-0.029375, +0.081266] |
| Context GCN — evidence/relation features | +0.003816 | [-0.004084, +0.011534] |
| LocalPlus — matched training-label update | +0.088580 | [-0.016859, +0.163112] |
| Updated LocalPlus — same soft processing | +0.088580 | [-0.016859, +0.163112] |
| Training-label frequency only | +0.096241 | [-0.028248, +0.193438] |
| LocalPlus — complete current-T0 curated seeds | +0.077217 | [-0.034039, +0.148685] |
| Development-selected context stacker | +0.003816 | [-0.004084, +0.011534] |
| Matched annotation-only prior at author Float32(0.99) | +0.092942 | [+0.020858, +0.263295] |

### native · NK · Cellular component

Full native/bootstrap protein frame: 32; proteins with residual positive labels: 32. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.292517 | 32 | 32 |
| DeepGO-SE — sequence model | 0.496994 | 32 | 32 |
| LocalPlus — same soft processing | 0.292517 | 32 | 32 |
| DeepGO-SE — same soft processing | 0.499010 | 32 | 32 |
| Fixed 50/50 combination | 0.385185 | 32 | 32 |
| Development-selected global weight | 0.385185 | 32 | 32 |
| LocalPlus — historical model axis | 0.292517 | 32 | 32 |
| DeepGO-SE — historical model axis | 0.496994 | 32 | 32 |
| Current nonexperimental annotations | 0.494226 | 32 | 32 |
| Context stacker — zero-layer MLP | 0.483193 | 32 | 32 |
| Context stacker — eight-layer GCN | 0.484211 | 32 | 32 |
| LocalPlus — matched training-label update | 0.301325 | 32 | 32 |
| Updated LocalPlus — same soft processing | 0.301325 | 32 | 32 |
| Training-label frequency only | 0.290909 | 32 | 32 |
| LocalPlus — complete current-T0 curated seeds | 0.311037 | 32 | 32 |
| Development-selected context stacker | 0.484211 | 32 | 32 |
| Selected stacker + legal T0 annotation prior | 0.515021 | 32 | 32 |
| Matched annotation-only prior at author Float32(0.99) | 0.494226 | 32 | 32 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — sequence model | +0.018027 | [-0.038069, +0.079002] |
| LocalPlus — same soft processing | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — same soft processing | +0.016012 | [-0.041755, +0.077452] |
| Fixed 50/50 combination | +0.129836 | [+0.063522, +0.185283] |
| Development-selected global weight | +0.129836 | [+0.063522, +0.185283] |
| LocalPlus — historical model axis | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — historical model axis | +0.018027 | [-0.038069, +0.079002] |
| Current nonexperimental annotations | +0.020795 | [-0.070987, +0.134587] |
| Context stacker — zero-layer MLP | +0.031828 | [-0.017220, +0.066599] |
| Context stacker — eight-layer GCN | +0.030811 | [+0.009729, +0.053684] |
| LocalPlus — matched training-label update | +0.213697 | [+0.130493, +0.305085] |
| Updated LocalPlus — same soft processing | +0.213697 | [+0.130493, +0.305085] |
| Training-label frequency only | +0.224112 | [+0.147162, +0.313339] |
| LocalPlus — complete current-T0 curated seeds | +0.203985 | [+0.120300, +0.290450] |
| Development-selected context stacker | +0.030811 | [+0.009729, +0.053684] |
| Matched annotation-only prior at author Float32(0.99) | +0.020795 | [-0.070987, +0.134587] |

### native · LK · Molecular function

Full native/bootstrap protein frame: 15; proteins with residual positive labels: 15. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.230216 | 15 | 15 |
| DeepGO-SE — sequence model | 0.500000 | 15 | 15 |
| LocalPlus — same soft processing | 0.230216 | 15 | 15 |
| DeepGO-SE — same soft processing | 0.523077 | 15 | 15 |
| Fixed 50/50 combination | 0.450000 | 15 | 15 |
| Development-selected global weight | 0.450000 | 15 | 15 |
| LocalPlus — historical model axis | 0.230216 | 15 | 15 |
| DeepGO-SE — historical model axis | 0.500000 | 15 | 15 |
| Current nonexperimental annotations | 0.556818 | 15 | 15 |
| Context stacker — zero-layer MLP | 0.550898 | 15 | 15 |
| Context stacker — eight-layer GCN | 0.564417 | 15 | 15 |
| LocalPlus — matched training-label update | 0.230216 | 15 | 15 |
| Updated LocalPlus — same soft processing | 0.230216 | 15 | 15 |
| Training-label frequency only | 0.128000 | 15 | 15 |
| LocalPlus — complete current-T0 curated seeds | 0.244275 | 15 | 15 |
| Development-selected context stacker | 0.550898 | 15 | 15 |
| Selected stacker + legal T0 annotation prior | 0.553672 | 15 | 15 |
| Matched annotation-only prior at author Float32(0.99) | 0.556818 | 15 | 15 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — sequence model | +0.053672 | [-0.051660, +0.116825] |
| LocalPlus — same soft processing | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — same soft processing | +0.030595 | [-0.067931, +0.112441] |
| Fixed 50/50 combination | +0.103672 | [-0.075268, +0.200581] |
| Development-selected global weight | +0.103672 | [-0.075268, +0.200581] |
| LocalPlus — historical model axis | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — historical model axis | +0.053672 | [-0.051660, +0.116825] |
| Current nonexperimental annotations | -0.003146 | [-0.074205, +0.067627] |
| Context stacker — zero-layer MLP | +0.002774 | [-0.017759, +0.037971] |
| Context stacker — eight-layer GCN | -0.010745 | [-0.052780, +0.035782] |
| LocalPlus — matched training-label update | +0.323456 | [+0.039310, +0.548922] |
| Updated LocalPlus — same soft processing | +0.323456 | [+0.039310, +0.548922] |
| Training-label frequency only | +0.425672 | [+0.237269, +0.581041] |
| LocalPlus — complete current-T0 curated seeds | +0.309398 | [+0.021476, +0.541223] |
| Development-selected context stacker | +0.002774 | [-0.017759, +0.037971] |
| Matched annotation-only prior at author Float32(0.99) | -0.003146 | [-0.074205, +0.067627] |

### native · LK · Biological process

Full native/bootstrap protein frame: 59; proteins with residual positive labels: 59. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.338317 | 59 | 59 |
| DeepGO-SE — sequence model | 0.311309 | 59 | 59 |
| LocalPlus — same soft processing | 0.338317 | 59 | 59 |
| DeepGO-SE — same soft processing | 0.313349 | 59 | 59 |
| Fixed 50/50 combination | 0.349601 | 59 | 59 |
| Development-selected global weight | 0.352655 | 59 | 59 |
| LocalPlus — historical model axis | 0.338317 | 59 | 59 |
| DeepGO-SE — historical model axis | 0.311309 | 59 | 59 |
| Current nonexperimental annotations | 0.361386 | 59 | 59 |
| Context stacker — zero-layer MLP | 0.395370 | 59 | 59 |
| Context stacker — eight-layer GCN | 0.391833 | 59 | 59 |
| Context GCN — evidence/relation features | 0.390567 | 59 | 59 |
| LocalPlus — matched training-label update | 0.337574 | 59 | 59 |
| Updated LocalPlus — same soft processing | 0.337574 | 59 | 59 |
| Training-label frequency only | 0.228750 | 59 | 59 |
| LocalPlus — complete current-T0 curated seeds | 0.358277 | 59 | 59 |
| Development-selected context stacker | 0.390567 | 59 | 59 |
| Selected stacker + legal T0 annotation prior | 0.390758 | 59 | 59 |
| Matched annotation-only prior at author Float32(0.99) | 0.361386 | 59 | 59 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.052441 | [+0.001758, +0.113378] |
| DeepGO-SE — sequence model | +0.079449 | [+0.027942, +0.141329] |
| LocalPlus — same soft processing | +0.052441 | [+0.001758, +0.113378] |
| DeepGO-SE — same soft processing | +0.077409 | [+0.025776, +0.138188] |
| Fixed 50/50 combination | +0.041157 | [-0.004321, +0.103933] |
| Development-selected global weight | +0.038103 | [-0.007858, +0.098558] |
| LocalPlus — historical model axis | +0.052441 | [+0.001758, +0.113378] |
| DeepGO-SE — historical model axis | +0.079449 | [+0.027942, +0.141329] |
| Current nonexperimental annotations | +0.029372 | [-0.008794, +0.082923] |
| Context stacker — zero-layer MLP | -0.004612 | [-0.026530, +0.024234] |
| Context stacker — eight-layer GCN | -0.001075 | [-0.022540, +0.019412] |
| Context GCN — evidence/relation features | +0.000191 | [-0.009799, +0.007679] |
| LocalPlus — matched training-label update | +0.053184 | [+0.001023, +0.112202] |
| Updated LocalPlus — same soft processing | +0.053184 | [+0.001023, +0.112202] |
| Training-label frequency only | +0.162008 | [+0.092658, +0.244600] |
| LocalPlus — complete current-T0 curated seeds | +0.032481 | [-0.020734, +0.088477] |
| Development-selected context stacker | +0.000191 | [-0.009799, +0.007679] |
| Matched annotation-only prior at author Float32(0.99) | +0.029372 | [-0.008794, +0.082923] |

### native · LK · Cellular component

Full native/bootstrap protein frame: 58; proteins with residual positive labels: 58. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.471369 | 58 | 58 |
| DeepGO-SE — sequence model | 0.542722 | 58 | 58 |
| LocalPlus — same soft processing | 0.471369 | 58 | 58 |
| DeepGO-SE — same soft processing | 0.549606 | 58 | 58 |
| Fixed 50/50 combination | 0.523364 | 58 | 58 |
| Development-selected global weight | 0.523364 | 58 | 58 |
| LocalPlus — historical model axis | 0.471369 | 58 | 58 |
| DeepGO-SE — historical model axis | 0.542722 | 58 | 58 |
| Current nonexperimental annotations | 0.554562 | 58 | 58 |
| Context stacker — zero-layer MLP | 0.549430 | 58 | 58 |
| Context stacker — eight-layer GCN | 0.587646 | 58 | 58 |
| LocalPlus — matched training-label update | 0.468051 | 58 | 58 |
| Updated LocalPlus — same soft processing | 0.468051 | 58 | 58 |
| Training-label frequency only | 0.435564 | 58 | 58 |
| LocalPlus — complete current-T0 curated seeds | 0.471545 | 58 | 58 |
| Development-selected context stacker | 0.587646 | 58 | 58 |
| Selected stacker + legal T0 annotation prior | 0.584767 | 58 | 58 |
| Matched annotation-only prior at author Float32(0.99) | 0.554562 | 58 | 58 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — sequence model | +0.042045 | [+0.000616, +0.074623] |
| LocalPlus — same soft processing | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — same soft processing | +0.035160 | [-0.003229, +0.069259] |
| Fixed 50/50 combination | +0.061402 | [+0.012169, +0.108570] |
| Development-selected global weight | +0.061402 | [+0.012169, +0.108570] |
| LocalPlus — historical model axis | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — historical model axis | +0.042045 | [+0.000616, +0.074623] |
| Current nonexperimental annotations | +0.030205 | [-0.033366, +0.105038] |
| Context stacker — zero-layer MLP | +0.035337 | [-0.000589, +0.064781] |
| Context stacker — eight-layer GCN | -0.002879 | [-0.015584, +0.010987] |
| LocalPlus — matched training-label update | +0.116715 | [+0.057477, +0.175678] |
| Updated LocalPlus — same soft processing | +0.116715 | [+0.057477, +0.175678] |
| Training-label frequency only | +0.149202 | [+0.076935, +0.229029] |
| LocalPlus — complete current-T0 curated seeds | +0.113222 | [+0.054824, +0.173421] |
| Development-selected context stacker | -0.002879 | [-0.015584, +0.010987] |
| Matched annotation-only prior at author Float32(0.99) | +0.030205 | [-0.033366, +0.105038] |

### fixed_T0 · PK · Molecular function

Full native/bootstrap protein frame: 228; proteins with residual positive labels: 228. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.127212 | 228 | 228 |
| DeepGO-SE — sequence model | 0.211432 | 228 | 228 |
| LocalPlus — same soft processing | 0.127212 | 228 | 228 |
| DeepGO-SE — same soft processing | 0.211921 | 228 | 228 |
| Fixed 50/50 combination | 0.213896 | 228 | 228 |
| Development-selected global weight | 0.213896 | 228 | 228 |
| LocalPlus — historical model axis | 0.127212 | 228 | 228 |
| DeepGO-SE — historical model axis | 0.211432 | 228 | 228 |
| Current nonexperimental annotations | 0.311316 | 228 | 228 |
| Context stacker — zero-layer MLP | 0.299478 | 228 | 228 |
| Context stacker — eight-layer GCN | 0.291419 | 228 | 228 |
| LocalPlus — matched training-label update | 0.132653 | 228 | 228 |
| Updated LocalPlus — same soft processing | 0.132653 | 228 | 228 |
| Training-label frequency only | 0.091826 | 228 | 228 |
| LocalPlus — complete current-T0 curated seeds | 0.139747 | 228 | 228 |
| Development-selected context stacker | 0.299478 | 228 | 228 |
| Selected stacker + legal T0 annotation prior | 0.309252 | 228 | 228 |
| Matched annotation-only prior at author Float32(0.99) | 0.311316 | 228 | 228 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.182040 | [+0.131530, +0.236471] |
| DeepGO-SE — sequence model | +0.097820 | [+0.061408, +0.138284] |
| LocalPlus — same soft processing | +0.182040 | [+0.131530, +0.236471] |
| DeepGO-SE — same soft processing | +0.097332 | [+0.059534, +0.137686] |
| Fixed 50/50 combination | +0.095356 | [+0.060610, +0.131601] |
| Development-selected global weight | +0.095356 | [+0.060610, +0.131601] |
| LocalPlus — historical model axis | +0.182040 | [+0.131530, +0.236471] |
| DeepGO-SE — historical model axis | +0.097820 | [+0.061408, +0.138284] |
| Current nonexperimental annotations | -0.002064 | [-0.022390, +0.031888] |
| Context stacker — zero-layer MLP | +0.009775 | [-0.001539, +0.028468] |
| Context stacker — eight-layer GCN | +0.017833 | [-0.007210, +0.036589] |
| LocalPlus — matched training-label update | +0.176599 | [+0.127856, +0.229969] |
| Updated LocalPlus — same soft processing | +0.176599 | [+0.127856, +0.229969] |
| Training-label frequency only | +0.217426 | [+0.169616, +0.275774] |
| LocalPlus — complete current-T0 curated seeds | +0.169505 | [+0.118664, +0.222803] |
| Development-selected context stacker | +0.009775 | [-0.001539, +0.028468] |
| Matched annotation-only prior at author Float32(0.99) | -0.002064 | [-0.022390, +0.031888] |

### fixed_T0 · PK · Biological process

Full native/bootstrap protein frame: 319; proteins with residual positive labels: 319. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.171550 | 319 | 319 |
| DeepGO-SE — sequence model | 0.131391 | 319 | 319 |
| LocalPlus — same soft processing | 0.171550 | 319 | 319 |
| DeepGO-SE — same soft processing | 0.132090 | 319 | 319 |
| Fixed 50/50 combination | 0.164958 | 319 | 319 |
| Development-selected global weight | 0.178030 | 319 | 319 |
| LocalPlus — historical model axis | 0.171550 | 319 | 319 |
| DeepGO-SE — historical model axis | 0.131391 | 319 | 319 |
| Current nonexperimental annotations | 0.146169 | 319 | 319 |
| Context stacker — zero-layer MLP | 0.194713 | 319 | 319 |
| Context stacker — eight-layer GCN | 0.182759 | 319 | 319 |
| Context GCN — evidence/relation features | 0.210093 | 319 | 319 |
| LocalPlus — matched training-label update | 0.175187 | 319 | 319 |
| Updated LocalPlus — same soft processing | 0.175187 | 319 | 319 |
| Training-label frequency only | 0.107277 | 319 | 319 |
| LocalPlus — complete current-T0 curated seeds | 0.182771 | 319 | 319 |
| Development-selected context stacker | 0.210093 | 319 | 319 |
| Selected stacker + legal T0 annotation prior | 0.190092 | 319 | 319 |
| Matched annotation-only prior at author Float32(0.99) | 0.146169 | 319 | 319 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.018542 | [-0.010186, +0.045480] |
| DeepGO-SE — sequence model | +0.058701 | [+0.035251, +0.083362] |
| LocalPlus — same soft processing | +0.018542 | [-0.010186, +0.045480] |
| DeepGO-SE — same soft processing | +0.058002 | [+0.033748, +0.082513] |
| Fixed 50/50 combination | +0.025135 | [+0.001075, +0.052139] |
| Development-selected global weight | +0.012062 | [-0.015403, +0.038518] |
| LocalPlus — historical model axis | +0.018542 | [-0.010186, +0.045480] |
| DeepGO-SE — historical model axis | +0.058701 | [+0.035251, +0.083362] |
| Current nonexperimental annotations | +0.043923 | [+0.028906, +0.059156] |
| Context stacker — zero-layer MLP | -0.004621 | [-0.021802, +0.012187] |
| Context stacker — eight-layer GCN | +0.007333 | [-0.007781, +0.022612] |
| Context GCN — evidence/relation features | -0.020001 | [-0.029046, -0.012877] |
| LocalPlus — matched training-label update | +0.014905 | [-0.013282, +0.043012] |
| Updated LocalPlus — same soft processing | +0.014905 | [-0.013282, +0.043012] |
| Training-label frequency only | +0.082815 | [+0.049400, +0.115643] |
| LocalPlus — complete current-T0 curated seeds | +0.007321 | [-0.022269, +0.036472] |
| Development-selected context stacker | -0.020001 | [-0.029046, -0.012877] |
| Matched annotation-only prior at author Float32(0.99) | +0.043923 | [+0.028906, +0.059156] |

### fixed_T0 · PK · Cellular component

Full native/bootstrap protein frame: 1230; proteins with residual positive labels: 1230. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.197996 | 1230 | 1230 |
| DeepGO-SE — sequence model | 0.180277 | 1230 | 1230 |
| LocalPlus — same soft processing | 0.197996 | 1230 | 1230 |
| DeepGO-SE — same soft processing | 0.182666 | 1230 | 1230 |
| Fixed 50/50 combination | 0.206327 | 1230 | 1230 |
| Development-selected global weight | 0.206327 | 1230 | 1230 |
| LocalPlus — historical model axis | 0.197996 | 1230 | 1230 |
| DeepGO-SE — historical model axis | 0.180277 | 1230 | 1230 |
| Current nonexperimental annotations | 0.335678 | 1230 | 1230 |
| Context stacker — zero-layer MLP | 0.220067 | 1230 | 1230 |
| Context stacker — eight-layer GCN | 0.267299 | 1230 | 1230 |
| LocalPlus — matched training-label update | 0.196825 | 1230 | 1230 |
| Updated LocalPlus — same soft processing | 0.196825 | 1230 | 1230 |
| Training-label frequency only | 0.109328 | 1230 | 1230 |
| LocalPlus — complete current-T0 curated seeds | 0.170379 | 1230 | 1230 |
| Development-selected context stacker | 0.267299 | 1230 | 1230 |
| Selected stacker + legal T0 annotation prior | 0.286030 | 1230 | 1230 |
| Matched annotation-only prior at author Float32(0.99) | 0.335678 | 1230 | 1230 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.088034 | [+0.069978, +0.105077] |
| DeepGO-SE — sequence model | +0.105752 | [+0.088806, +0.122588] |
| LocalPlus — same soft processing | +0.088034 | [+0.069978, +0.105077] |
| DeepGO-SE — same soft processing | +0.103364 | [+0.086090, +0.120230] |
| Fixed 50/50 combination | +0.079703 | [+0.062623, +0.095251] |
| Development-selected global weight | +0.079703 | [+0.062623, +0.095251] |
| LocalPlus — historical model axis | +0.088034 | [+0.069978, +0.105077] |
| DeepGO-SE — historical model axis | +0.105752 | [+0.088806, +0.122588] |
| Current nonexperimental annotations | -0.049649 | [-0.061581, -0.035885] |
| Context stacker — zero-layer MLP | +0.065963 | [+0.055208, +0.076299] |
| Context stacker — eight-layer GCN | +0.018731 | [+0.012387, +0.024483] |
| LocalPlus — matched training-label update | +0.089204 | [+0.071421, +0.106137] |
| Updated LocalPlus — same soft processing | +0.089204 | [+0.071421, +0.106137] |
| Training-label frequency only | +0.176702 | [+0.157927, +0.195628] |
| LocalPlus — complete current-T0 curated seeds | +0.115650 | [+0.097795, +0.132373] |
| Development-selected context stacker | +0.018731 | [+0.012387, +0.024483] |
| Matched annotation-only prior at author Float32(0.99) | -0.049649 | [-0.061581, -0.035885] |

### fixed_T0 · NK · Molecular function

Full native/bootstrap protein frame: 7; proteins with residual positive labels: 7. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.210526 | 7 | 7 |
| DeepGO-SE — sequence model | 0.405229 | 7 | 7 |
| LocalPlus — same soft processing | 0.210526 | 7 | 7 |
| DeepGO-SE — same soft processing | 0.400000 | 7 | 7 |
| Fixed 50/50 combination | 0.389610 | 7 | 7 |
| Development-selected global weight | 0.389610 | 7 | 7 |
| LocalPlus — historical model axis | 0.210526 | 7 | 7 |
| DeepGO-SE — historical model axis | 0.405229 | 7 | 7 |
| Current nonexperimental annotations | 0.433333 | 7 | 7 |
| Context stacker — zero-layer MLP | 0.387597 | 7 | 7 |
| Context stacker — eight-layer GCN | 0.396396 | 7 | 7 |
| LocalPlus — matched training-label update | 0.210526 | 7 | 7 |
| Updated LocalPlus — same soft processing | 0.210526 | 7 | 7 |
| Training-label frequency only | 0.187919 | 7 | 7 |
| LocalPlus — complete current-T0 curated seeds | 0.237037 | 7 | 7 |
| Development-selected context stacker | 0.387597 | 7 | 7 |
| Selected stacker + legal T0 annotation prior | 0.396825 | 7 | 7 |
| Matched annotation-only prior at author Float32(0.99) | 0.433333 | 7 | 7 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — sequence model | -0.008403 | [-0.137480, +0.216477] |
| LocalPlus — same soft processing | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — same soft processing | -0.003175 | [-0.146285, +0.218288] |
| Fixed 50/50 combination | +0.007215 | [-0.066849, +0.130087] |
| Development-selected global weight | +0.007215 | [-0.066849, +0.130087] |
| LocalPlus — historical model axis | +0.186299 | [-0.001305, +0.411064] |
| DeepGO-SE — historical model axis | -0.008403 | [-0.137480, +0.216477] |
| Current nonexperimental annotations | -0.036508 | [-0.145736, +0.111712] |
| Context stacker — zero-layer MLP | +0.009228 | [-0.004299, +0.032293] |
| Context stacker — eight-layer GCN | +0.000429 | [-0.159879, +0.120884] |
| LocalPlus — matched training-label update | +0.186299 | [-0.021289, +0.411064] |
| Updated LocalPlus — same soft processing | +0.186299 | [-0.021289, +0.411064] |
| Training-label frequency only | +0.208906 | [+0.034264, +0.436431] |
| LocalPlus — complete current-T0 curated seeds | +0.159788 | [-0.044920, +0.411770] |
| Development-selected context stacker | +0.009228 | [-0.004299, +0.032293] |
| Matched annotation-only prior at author Float32(0.99) | -0.036508 | [-0.145736, +0.111712] |

### fixed_T0 · NK · Biological process

Full native/bootstrap protein frame: 8; proteins with residual positive labels: 8. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.214925 | 8 | 8 |
| DeepGO-SE — sequence model | 0.301205 | 8 | 8 |
| LocalPlus — same soft processing | 0.214925 | 8 | 8 |
| DeepGO-SE — same soft processing | 0.303867 | 8 | 8 |
| Fixed 50/50 combination | 0.310249 | 8 | 8 |
| Development-selected global weight | 0.264249 | 8 | 8 |
| LocalPlus — historical model axis | 0.214925 | 8 | 8 |
| DeepGO-SE — historical model axis | 0.301205 | 8 | 8 |
| Current nonexperimental annotations | 0.223108 | 8 | 8 |
| Context stacker — zero-layer MLP | 0.318339 | 8 | 8 |
| Context stacker — eight-layer GCN | 0.284790 | 8 | 8 |
| Context GCN — evidence/relation features | 0.312727 | 8 | 8 |
| LocalPlus — matched training-label update | 0.227129 | 8 | 8 |
| Updated LocalPlus — same soft processing | 0.227129 | 8 | 8 |
| Training-label frequency only | 0.219697 | 8 | 8 |
| LocalPlus — complete current-T0 curated seeds | 0.238213 | 8 | 8 |
| Development-selected context stacker | 0.312727 | 8 | 8 |
| Selected stacker + legal T0 annotation prior | 0.316547 | 8 | 8 |
| Matched annotation-only prior at author Float32(0.99) | 0.223108 | 8 | 8 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.101621 | [-0.017258, +0.170352] |
| DeepGO-SE — sequence model | +0.015342 | [-0.114921, +0.103784] |
| LocalPlus — same soft processing | +0.101621 | [-0.017258, +0.170352] |
| DeepGO-SE — same soft processing | +0.012679 | [-0.112286, +0.095271] |
| Fixed 50/50 combination | +0.006297 | [-0.113220, +0.078107] |
| Development-selected global weight | +0.052298 | [-0.067182, +0.123636] |
| LocalPlus — historical model axis | +0.101621 | [-0.017258, +0.170352] |
| DeepGO-SE — historical model axis | +0.015342 | [-0.114921, +0.103784] |
| Current nonexperimental annotations | +0.093439 | [+0.020844, +0.263992] |
| Context stacker — zero-layer MLP | -0.001792 | [-0.024306, +0.033827] |
| Context stacker — eight-layer GCN | +0.031757 | [-0.029924, +0.081508] |
| Context GCN — evidence/relation features | +0.003819 | [-0.004235, +0.011568] |
| LocalPlus — matched training-label update | +0.089417 | [-0.013222, +0.164099] |
| Updated LocalPlus — same soft processing | +0.089417 | [-0.013222, +0.164099] |
| Training-label frequency only | +0.096850 | [-0.029680, +0.195182] |
| LocalPlus — complete current-T0 curated seeds | +0.078333 | [-0.033360, +0.150249] |
| Development-selected context stacker | +0.003819 | [-0.004235, +0.011568] |
| Matched annotation-only prior at author Float32(0.99) | +0.093439 | [+0.020844, +0.263992] |

### fixed_T0 · NK · Cellular component

Full native/bootstrap protein frame: 32; proteins with residual positive labels: 32. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.292517 | 32 | 32 |
| DeepGO-SE — sequence model | 0.496994 | 32 | 32 |
| LocalPlus — same soft processing | 0.292517 | 32 | 32 |
| DeepGO-SE — same soft processing | 0.499010 | 32 | 32 |
| Fixed 50/50 combination | 0.385185 | 32 | 32 |
| Development-selected global weight | 0.385185 | 32 | 32 |
| LocalPlus — historical model axis | 0.292517 | 32 | 32 |
| DeepGO-SE — historical model axis | 0.496994 | 32 | 32 |
| Current nonexperimental annotations | 0.494226 | 32 | 32 |
| Context stacker — zero-layer MLP | 0.483193 | 32 | 32 |
| Context stacker — eight-layer GCN | 0.484211 | 32 | 32 |
| LocalPlus — matched training-label update | 0.301325 | 32 | 32 |
| Updated LocalPlus — same soft processing | 0.301325 | 32 | 32 |
| Training-label frequency only | 0.290909 | 32 | 32 |
| LocalPlus — complete current-T0 curated seeds | 0.311037 | 32 | 32 |
| Development-selected context stacker | 0.484211 | 32 | 32 |
| Selected stacker + legal T0 annotation prior | 0.515021 | 32 | 32 |
| Matched annotation-only prior at author Float32(0.99) | 0.494226 | 32 | 32 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — sequence model | +0.018027 | [-0.038069, +0.079002] |
| LocalPlus — same soft processing | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — same soft processing | +0.016012 | [-0.041755, +0.077452] |
| Fixed 50/50 combination | +0.129836 | [+0.063522, +0.185283] |
| Development-selected global weight | +0.129836 | [+0.063522, +0.185283] |
| LocalPlus — historical model axis | +0.222504 | [+0.134584, +0.306536] |
| DeepGO-SE — historical model axis | +0.018027 | [-0.038069, +0.079002] |
| Current nonexperimental annotations | +0.020795 | [-0.070987, +0.134587] |
| Context stacker — zero-layer MLP | +0.031828 | [-0.017220, +0.066599] |
| Context stacker — eight-layer GCN | +0.030811 | [+0.009729, +0.053684] |
| LocalPlus — matched training-label update | +0.213697 | [+0.130493, +0.305085] |
| Updated LocalPlus — same soft processing | +0.213697 | [+0.130493, +0.305085] |
| Training-label frequency only | +0.224112 | [+0.147162, +0.313339] |
| LocalPlus — complete current-T0 curated seeds | +0.203985 | [+0.120300, +0.290342] |
| Development-selected context stacker | +0.030811 | [+0.009729, +0.053684] |
| Matched annotation-only prior at author Float32(0.99) | +0.020795 | [-0.070987, +0.134587] |

### fixed_T0 · LK · Molecular function

Full native/bootstrap protein frame: 15; proteins with residual positive labels: 15. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.230216 | 15 | 15 |
| DeepGO-SE — sequence model | 0.500000 | 15 | 15 |
| LocalPlus — same soft processing | 0.230216 | 15 | 15 |
| DeepGO-SE — same soft processing | 0.523077 | 15 | 15 |
| Fixed 50/50 combination | 0.450000 | 15 | 15 |
| Development-selected global weight | 0.450000 | 15 | 15 |
| LocalPlus — historical model axis | 0.230216 | 15 | 15 |
| DeepGO-SE — historical model axis | 0.500000 | 15 | 15 |
| Current nonexperimental annotations | 0.556818 | 15 | 15 |
| Context stacker — zero-layer MLP | 0.550898 | 15 | 15 |
| Context stacker — eight-layer GCN | 0.564417 | 15 | 15 |
| LocalPlus — matched training-label update | 0.230216 | 15 | 15 |
| Updated LocalPlus — same soft processing | 0.230216 | 15 | 15 |
| Training-label frequency only | 0.128000 | 15 | 15 |
| LocalPlus — complete current-T0 curated seeds | 0.244275 | 15 | 15 |
| Development-selected context stacker | 0.550898 | 15 | 15 |
| Selected stacker + legal T0 annotation prior | 0.553672 | 15 | 15 |
| Matched annotation-only prior at author Float32(0.99) | 0.556818 | 15 | 15 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — sequence model | +0.053672 | [-0.051660, +0.116825] |
| LocalPlus — same soft processing | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — same soft processing | +0.030595 | [-0.067931, +0.112441] |
| Fixed 50/50 combination | +0.103672 | [-0.075268, +0.200581] |
| Development-selected global weight | +0.103672 | [-0.075268, +0.200581] |
| LocalPlus — historical model axis | +0.323456 | [+0.039310, +0.547331] |
| DeepGO-SE — historical model axis | +0.053672 | [-0.051660, +0.116825] |
| Current nonexperimental annotations | -0.003146 | [-0.074205, +0.067627] |
| Context stacker — zero-layer MLP | +0.002774 | [-0.017759, +0.037971] |
| Context stacker — eight-layer GCN | -0.010745 | [-0.052780, +0.035782] |
| LocalPlus — matched training-label update | +0.323456 | [+0.039310, +0.548922] |
| Updated LocalPlus — same soft processing | +0.323456 | [+0.039310, +0.548922] |
| Training-label frequency only | +0.425672 | [+0.237269, +0.581041] |
| LocalPlus — complete current-T0 curated seeds | +0.309398 | [+0.021476, +0.541223] |
| Development-selected context stacker | +0.002774 | [-0.017759, +0.037971] |
| Matched annotation-only prior at author Float32(0.99) | -0.003146 | [-0.074205, +0.067627] |

### fixed_T0 · LK · Biological process

Full native/bootstrap protein frame: 59; proteins with residual positive labels: 59. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.340171 | 59 | 59 |
| DeepGO-SE — sequence model | 0.313185 | 59 | 59 |
| LocalPlus — same soft processing | 0.340171 | 59 | 59 |
| DeepGO-SE — same soft processing | 0.315253 | 59 | 59 |
| Fixed 50/50 combination | 0.351687 | 59 | 59 |
| Development-selected global weight | 0.354776 | 59 | 59 |
| LocalPlus — historical model axis | 0.340171 | 59 | 59 |
| DeepGO-SE — historical model axis | 0.313185 | 59 | 59 |
| Current nonexperimental annotations | 0.360575 | 59 | 59 |
| Context stacker — zero-layer MLP | 0.394366 | 59 | 59 |
| Context stacker — eight-layer GCN | 0.389590 | 59 | 59 |
| Context GCN — evidence/relation features | 0.388728 | 59 | 59 |
| LocalPlus — matched training-label update | 0.339415 | 59 | 59 |
| Updated LocalPlus — same soft processing | 0.339415 | 59 | 59 |
| Training-label frequency only | 0.228840 | 59 | 59 |
| LocalPlus — complete current-T0 curated seeds | 0.359870 | 59 | 59 |
| Development-selected context stacker | 0.388728 | 59 | 59 |
| Selected stacker + legal T0 annotation prior | 0.388460 | 59 | 59 |
| Matched annotation-only prior at author Float32(0.99) | 0.360575 | 59 | 59 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.048289 | [+0.000307, +0.102732] |
| DeepGO-SE — sequence model | +0.075275 | [+0.027409, +0.129772] |
| LocalPlus — same soft processing | +0.048289 | [+0.000307, +0.102732] |
| DeepGO-SE — same soft processing | +0.073207 | [+0.025159, +0.126067] |
| Fixed 50/50 combination | +0.036773 | [-0.005169, +0.087900] |
| Development-selected global weight | +0.033684 | [-0.008712, +0.084321] |
| LocalPlus — historical model axis | +0.048289 | [+0.000307, +0.102732] |
| DeepGO-SE — historical model axis | +0.075275 | [+0.027409, +0.129772] |
| Current nonexperimental annotations | +0.027885 | [-0.010577, +0.081985] |
| Context stacker — zero-layer MLP | -0.005906 | [-0.027381, +0.023190] |
| Context stacker — eight-layer GCN | -0.001130 | [-0.021876, +0.018843] |
| Context GCN — evidence/relation features | -0.000268 | [-0.009304, +0.006297] |
| LocalPlus — matched training-label update | +0.049045 | [-0.001550, +0.101446] |
| Updated LocalPlus — same soft processing | +0.049045 | [-0.001550, +0.101446] |
| Training-label frequency only | +0.159620 | [+0.094731, +0.236106] |
| LocalPlus — complete current-T0 curated seeds | +0.028590 | [-0.021647, +0.077879] |
| Development-selected context stacker | -0.000268 | [-0.009304, +0.006297] |
| Matched annotation-only prior at author Float32(0.99) | +0.027885 | [-0.010577, +0.081985] |

### fixed_T0 · LK · Cellular component

Full native/bootstrap protein frame: 58; proteins with residual positive labels: 58. Matched-prior parity: passed.

| Method | Ordinary micro-Fmax | Raw protein rows | Residual-positive proteins |
|---|---|---|---|
| LocalPlus — retained annotations | 0.471369 | 58 | 58 |
| DeepGO-SE — sequence model | 0.542722 | 58 | 58 |
| LocalPlus — same soft processing | 0.471369 | 58 | 58 |
| DeepGO-SE — same soft processing | 0.549606 | 58 | 58 |
| Fixed 50/50 combination | 0.523364 | 58 | 58 |
| Development-selected global weight | 0.523364 | 58 | 58 |
| LocalPlus — historical model axis | 0.471369 | 58 | 58 |
| DeepGO-SE — historical model axis | 0.542722 | 58 | 58 |
| Current nonexperimental annotations | 0.557554 | 58 | 58 |
| Context stacker — zero-layer MLP | 0.549430 | 58 | 58 |
| Context stacker — eight-layer GCN | 0.587646 | 58 | 58 |
| LocalPlus — matched training-label update | 0.468051 | 58 | 58 |
| Updated LocalPlus — same soft processing | 0.468051 | 58 | 58 |
| Training-label frequency only | 0.435564 | 58 | 58 |
| LocalPlus — complete current-T0 curated seeds | 0.471545 | 58 | 58 |
| Development-selected context stacker | 0.587646 | 58 | 58 |
| Selected stacker + legal T0 annotation prior | 0.584767 | 58 | 58 |
| Matched annotation-only prior at author Float32(0.99) | 0.557554 | 58 | 58 |

| Selected + prior versus control | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|
| LocalPlus — retained annotations | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — sequence model | +0.042045 | [+0.000616, +0.074623] |
| LocalPlus — same soft processing | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — same soft processing | +0.035160 | [-0.003229, +0.069259] |
| Fixed 50/50 combination | +0.061402 | [+0.012169, +0.108570] |
| Development-selected global weight | +0.061402 | [+0.012169, +0.108570] |
| LocalPlus — historical model axis | +0.113397 | [+0.057992, +0.175136] |
| DeepGO-SE — historical model axis | +0.042045 | [+0.000616, +0.074623] |
| Current nonexperimental annotations | +0.027213 | [-0.034946, +0.100485] |
| Context stacker — zero-layer MLP | +0.035337 | [-0.000589, +0.064781] |
| Context stacker — eight-layer GCN | -0.002879 | [-0.015584, +0.010987] |
| LocalPlus — matched training-label update | +0.116715 | [+0.057477, +0.175678] |
| Updated LocalPlus — same soft processing | +0.116715 | [+0.057477, +0.175678] |
| Training-label frequency only | +0.149202 | [+0.076935, +0.229029] |
| LocalPlus — complete current-T0 curated seeds | +0.113222 | [+0.054824, +0.173421] |
| Development-selected context stacker | -0.002879 | [-0.015584, +0.010987] |
| Matched annotation-only prior at author Float32(0.99) | +0.027213 | [-0.034946, +0.100485] |

## Method and limits

- The author’s final CAFA6 operation concatenates predictions and annotation rows scored as Float32(0.99), then takes MAX for each literal target/term key. Here only the original sealed strict T0 nonexperimental prior replaces the author’s competition-known-label input. This is an explicit input adaptation, not reproduction of the full CAFA6 pipeline.

- All 3,300 target rows and the complete literal union of model and prior heads are preserved. The merge follows the already completed soft processing. Only the unchanged evaluator canonicalization and upward fill follow; no additional MIN/soft pass, fitting, retrieval or outcome-based routing was introduced.

- The matched annotation-only 0.99 arm uses the same union axis with an exactly zero model. Each available native Fmax point and all 2,000 paired-draw peaks must exactly match the original score-1 annotation prior. Complete threshold curves need not be identical above 0.99. This gate checks integration, not biological superiority.

- Every original method remains visible. The saved intervals compare the merged candidate with every available original method and the matched prior. The matched prior is an algebraic integration control; no additional pairwise intervals were invented for it.

- PK means partial knowledge: the unchanged native evaluator excludes T0-known functions. NK and LK retain their original no/limited-knowledge definitions. MF, BP and CC describe molecular function, biological process and cellular component. Native and fixed-T0 denote different ontology/reference views.

- The reference measures recovery of later-snapshot curated annotations. It does not establish first public knowledge, publication dates, independent experiments or a percentage of biologically correct Pharos edges. Annotations are incomplete; an unmatched prediction is not established false.

- This follow-up was chosen after the reference was opened. Even a favorable development interval requires independent confirmation on an untouched reference. There is no new success gate, model selection, automatic graph pruning, application-default change or clinical claim.

Source: [pinned CAFA6 author operation](https://github.com/btbpanda/CAFA6-updates/blob/0ee85d2f07f724be1721ea39211f1b364535f976/model_scripts/postproc_and_sub.py).
