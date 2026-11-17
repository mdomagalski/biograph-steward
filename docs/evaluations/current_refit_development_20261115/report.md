# Current-annotation refit and source controls

**DEVELOPMENT — reference already consumed; no independent confirmation.**

One fixed biological-process refit adds legal pre-cutoff curated positives while retaining every historical fitting positive. Two information-union controls test whether a simpler source update explains the result. All six original BP cells and every declared control remain visible, including losses and unavailable intervals.

The source-admitted update retains 208,835 positive fitting memberships and adds 1,941 across 161 of the same 4,040 proteins, giving 210,776 memberships and 3,567 root-positive fitting proteins. Memberships are annotations, not independent studies. The fixed output vocabulary, raw parent forecasts and final 3,300-target frame remain unchanged.

## PK overview

| Method | Native-view micro-Fmax | Fixed-T0-view micro-Fmax |
|---|---|---|
| LocalPlus — retained annotations | 0.054732 | 0.171550 |
| Development-selected context stacker | 0.073431 | 0.210093 |
| LocalPlus — complete current-T0 curated seeds | 0.058838 | 0.182771 |
| LocalPlus — retained and current curated seed union | 0.055952 | 0.176917 |
| Direct prior — current nonexperimental + retained curated annotations | 0.023529 | 0.133967 |
| Context GCN — current-T0 positive-union refit | 0.073062 | 0.196834 |
| Current nonexperimental annotations | 0.025476 | 0.146169 |

PK means partial knowledge: T0-known functions are excluded by the unchanged evaluator. NK and LK retain the original no-knowledge and limited-knowledge definitions. Fmax uses the original .001–.999 threshold grid. Compare methods within one view; native and fixed-T0 views have different reference populations. Paired 95% intervals below are copied from the saved 2,000 whole-protein draws. They are conditional, unadjusted development descriptions.

## All six BP cells

### native · PK · Biological process

Full native protein frame: 1954; proteins with residual positive labels: 322.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.054732 | [0.042066, 0.072232] | 1954 | 322 |
| DeepGO-SE — sequence model | evaluated | 0.036422 | [0.028909, 0.045569] | 1954 | 322 |
| LocalPlus — same soft processing | evaluated | 0.054732 | [0.042066, 0.072232] | 1954 | 322 |
| DeepGO-SE — same soft processing | evaluated | 0.037041 | [0.029211, 0.046434] | 1954 | 322 |
| Fixed 50/50 combination | evaluated | 0.048155 | [0.037372, 0.062610] | 1954 | 322 |
| Development-selected global weight | evaluated | 0.056100 | [0.044164, 0.072801] | 1954 | 322 |
| LocalPlus — historical model axis | evaluated | 0.054732 | [0.042066, 0.072232] | 1954 | 322 |
| DeepGO-SE — historical model axis | evaluated | 0.036422 | [0.028909, 0.045569] | 1954 | 322 |
| Current nonexperimental annotations | evaluated | 0.025476 | [0.019932, 0.031437] | 1954 | 322 |
| Context stacker — zero-layer MLP | evaluated | 0.061746 | [0.048317, 0.077489] | 1954 | 322 |
| Context stacker — eight-layer GCN | evaluated | 0.059725 | [0.047753, 0.076513] | 1954 | 322 |
| Context GCN — evidence/relation features | evaluated | 0.073431 | [0.056718, 0.096615] | 1954 | 322 |
| LocalPlus — matched training-label update | evaluated | 0.055296 | [0.042995, 0.072549] | 1954 | 322 |
| Updated LocalPlus — same soft processing | evaluated | 0.055296 | [0.042995, 0.072549] | 1954 | 322 |
| Training-label frequency only | evaluated | 0.032584 | [0.024920, 0.042433] | 1954 | 322 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.058838 | [0.045650, 0.076908] | 1954 | 322 |
| Development-selected context stacker | evaluated | 0.073431 | [0.056718, 0.096615] | 1954 | 322 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.046331 | [0.036452, 0.059083] | 1954 | 322 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.025476 | [0.019932, 0.031437] | 1954 | 322 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.073062 | [0.055289, 0.094441] | 1954 | 322 |
| LocalPlus — retained and current curated seed union | evaluated | 0.055952 | [0.043946, 0.073965] | 1954 | 322 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.023529 | [0.018816, 0.028750] | 1954 | 322 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.018330 | [+0.002136, +0.034334] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.036640 | [+0.023580, +0.052905] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.018330 | [+0.002136, +0.034334] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.036021 | [+0.023092, +0.052466] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.024907 | [+0.010254, +0.040942] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.016962 | [+0.001577, +0.031802] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.018330 | [+0.002136, +0.034334] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.036640 | [+0.023580, +0.052905] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.047586 | [+0.034547, +0.064654] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | +0.011316 | [+0.001035, +0.023171] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.013336 | [+0.002372, +0.023828] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | -0.000369 | [-0.009663, +0.008049] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.017766 | [+0.001847, +0.033466] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.017766 | [+0.001847, +0.033466] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.040478 | [+0.023143, +0.059838] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.014224 | [-0.002008, +0.030450] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | -0.000369 | [-0.009663, +0.008049] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.026731 | [+0.017421, +0.038478] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.047586 | [+0.034547, +0.064654] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.017110 | [-0.000076, +0.032285] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.049532 | [+0.035881, +0.067092] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.001220 | [-0.000532, +0.004776] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.000656 | [-0.000670, +0.003479] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.002886 | [-0.004860, +0.000672] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.017479 | [-0.033957, -0.000728] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | +0.030476 | [+0.020007, +0.047625] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | -0.031202 | [-0.047889, -0.020070] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | -0.031766 | [-0.047837, -0.020889] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.035308 | [-0.052547, -0.023902] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.049902 | [-0.069249, -0.036878] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | -0.001946 | [-0.003121, -0.000668] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.032423 | [+0.021987, +0.049606] |

### native · NK · Biological process

Full native protein frame: 8; proteins with residual positive labels: 8.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.213650 | [0.161137, 0.328617] | 8 | 8 |
| DeepGO-SE — sequence model | evaluated | 0.299401 | [0.209147, 0.419804] | 8 | 8 |
| LocalPlus — same soft processing | evaluated | 0.213650 | [0.161137, 0.328617] | 8 | 8 |
| DeepGO-SE — same soft processing | evaluated | 0.301370 | [0.209150, 0.420606] | 8 | 8 |
| Fixed 50/50 combination | evaluated | 0.308540 | [0.212963, 0.424269] | 8 | 8 |
| Development-selected global weight | evaluated | 0.262887 | [0.184206, 0.398212] | 8 | 8 |
| LocalPlus — historical model axis | evaluated | 0.213650 | [0.161137, 0.328617] | 8 | 8 |
| DeepGO-SE — historical model axis | evaluated | 0.299401 | [0.209147, 0.419804] | 8 | 8 |
| Current nonexperimental annotations | evaluated | 0.221344 | [0.021733, 0.390805] | 8 | 8 |
| Context stacker — zero-layer MLP | evaluated | 0.316151 | [0.173913, 0.433142] | 8 | 8 |
| Context stacker — eight-layer GCN | evaluated | 0.282958 | [0.187173, 0.391475] | 8 | 8 |
| Context GCN — evidence/relation features | evaluated | 0.310469 | [0.181818, 0.430175] | 8 | 8 |
| LocalPlus — matched training-label update | evaluated | 0.225705 | [0.160914, 0.321224] | 8 | 8 |
| Updated LocalPlus — same soft processing | evaluated | 0.225705 | [0.160914, 0.321224] | 8 | 8 |
| Training-label frequency only | evaluated | 0.218045 | [0.157358, 0.323088] | 8 | 8 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.237069 | [0.169484, 0.357012] | 8 | 8 |
| Development-selected context stacker | evaluated | 0.310469 | [0.181818, 0.430175] | 8 | 8 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.314286 | [0.179464, 0.440368] | 8 | 8 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.221344 | [0.021733, 0.390805] | 8 | 8 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.315789 | [0.172369, 0.456623] | 8 | 8 |
| LocalPlus — retained and current curated seed union | evaluated | 0.233533 | [0.164698, 0.348039] | 8 | 8 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.221344 | [0.021733, 0.390805] | 8 | 8 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.102140 | [-0.025660, +0.175567] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.016388 | [-0.124949, +0.105052] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.102140 | [-0.025660, +0.175567] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.014420 | [-0.122034, +0.096408] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.007250 | [-0.122959, +0.082734] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.052903 | [-0.077385, +0.122111] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.102140 | [-0.025660, +0.175567] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.016388 | [-0.124949, +0.105052] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.094446 | [+0.022240, +0.273034] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | -0.000362 | [-0.025561, +0.043068] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.032831 | [-0.031905, +0.080122] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | +0.005320 | [-0.014378, +0.036490] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.090084 | [-0.021095, +0.173788] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.090084 | [-0.021095, +0.173788] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.097744 | [-0.035837, +0.199191] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.078721 | [-0.037285, +0.156686] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | +0.005320 | [-0.014378, +0.036490] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.001504 | [-0.011586, +0.029334] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.094446 | [+0.022240, +0.273034] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.082257 | [-0.034212, +0.161241] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.094446 | [+0.022240, +0.273034] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.019883 | [-0.009400, +0.035294] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.007828 | [-0.006182, +0.033508] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.003536 | [-0.016758, +0.019640] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.076936 | [-0.149218, +0.026616] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | +0.012189 | [-0.098274, +0.205382] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | +0.007694 | [-0.192306, +0.111994] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | -0.004361 | [-0.195037, +0.109466] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.015725 | [-0.198898, +0.087815] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.089125 | [-0.263381, -0.011584] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | +0.000000 | [+0.000000, +0.000000] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.012189 | [-0.098274, +0.205382] |

### native · LK · Biological process

Full native protein frame: 59; proteins with residual positive labels: 59.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.338317 | [0.296161, 0.398188] | 59 | 59 |
| DeepGO-SE — sequence model | evaluated | 0.311309 | [0.272417, 0.360494] | 59 | 59 |
| LocalPlus — same soft processing | evaluated | 0.338317 | [0.296161, 0.398188] | 59 | 59 |
| DeepGO-SE — same soft processing | evaluated | 0.313349 | [0.274444, 0.365218] | 59 | 59 |
| Fixed 50/50 combination | evaluated | 0.349601 | [0.306418, 0.402624] | 59 | 59 |
| Development-selected global weight | evaluated | 0.352655 | [0.308113, 0.412971] | 59 | 59 |
| LocalPlus — historical model axis | evaluated | 0.338317 | [0.296161, 0.398188] | 59 | 59 |
| DeepGO-SE — historical model axis | evaluated | 0.311309 | [0.272417, 0.360494] | 59 | 59 |
| Current nonexperimental annotations | evaluated | 0.361386 | [0.275809, 0.452413] | 59 | 59 |
| Context stacker — zero-layer MLP | evaluated | 0.395370 | [0.334949, 0.467236] | 59 | 59 |
| Context stacker — eight-layer GCN | evaluated | 0.391833 | [0.339467, 0.463220] | 59 | 59 |
| Context GCN — evidence/relation features | evaluated | 0.390567 | [0.335456, 0.462674] | 59 | 59 |
| LocalPlus — matched training-label update | evaluated | 0.337574 | [0.298329, 0.400371] | 59 | 59 |
| Updated LocalPlus — same soft processing | evaluated | 0.337574 | [0.298329, 0.400371] | 59 | 59 |
| Training-label frequency only | evaluated | 0.228750 | [0.198005, 0.267225] | 59 | 59 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.358277 | [0.313902, 0.425854] | 59 | 59 |
| Development-selected context stacker | evaluated | 0.390567 | [0.335456, 0.462674] | 59 | 59 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.390758 | [0.335311, 0.460574] | 59 | 59 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.361386 | [0.275809, 0.452413] | 59 | 59 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.399080 | [0.339161, 0.471010] | 59 | 59 |
| LocalPlus — retained and current curated seed union | evaluated | 0.347656 | [0.308353, 0.417366] | 59 | 59 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.345886 | [0.262184, 0.438515] | 59 | 59 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.060764 | [+0.005240, +0.120011] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.087771 | [+0.038727, +0.143094] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.060764 | [+0.005240, +0.120011] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.085731 | [+0.036462, +0.141044] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.049480 | [+0.004418, +0.105863] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.046426 | [-0.003841, +0.104562] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.060764 | [+0.005240, +0.120011] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.087771 | [+0.038727, +0.143094] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.037694 | [-0.002803, +0.087912] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | +0.003710 | [-0.026493, +0.033860] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.007248 | [-0.022215, +0.031889] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | +0.008514 | [-0.014465, +0.030960] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.061506 | [+0.003312, +0.118924] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.061506 | [+0.003312, +0.118924] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.170330 | [+0.096189, +0.253905] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.040804 | [-0.015548, +0.097918] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | +0.008514 | [-0.014465, +0.030960] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.008322 | [-0.011625, +0.026579] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.037694 | [-0.002803, +0.087912] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.051424 | [-0.010265, +0.107890] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.053195 | [+0.010418, +0.103936] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.009339 | [-0.002163, +0.028186] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.010082 | [-0.001642, +0.025067] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.010620 | [-0.019605, +0.005150] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.042911 | [-0.098828, +0.011057] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | -0.013730 | [-0.088068, +0.078089] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | +0.007569 | [-0.076785, +0.086571] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | +0.008311 | [-0.079288, +0.085115] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.012391 | [-0.097971, +0.061938] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.044681 | [-0.102676, -0.002170] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | -0.015501 | [-0.047294, +0.000000] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.001771 | [-0.072257, +0.091302] |

### fixed_T0 · PK · Biological process

Full native protein frame: 319; proteins with residual positive labels: 319.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.171550 | [0.148580, 0.200863] | 319 | 319 |
| DeepGO-SE — sequence model | evaluated | 0.131391 | [0.111653, 0.156202] | 319 | 319 |
| LocalPlus — same soft processing | evaluated | 0.171550 | [0.148580, 0.200863] | 319 | 319 |
| DeepGO-SE — same soft processing | evaluated | 0.132090 | [0.112288, 0.157544] | 319 | 319 |
| Fixed 50/50 combination | evaluated | 0.164958 | [0.141274, 0.192150] | 319 | 319 |
| Development-selected global weight | evaluated | 0.178030 | [0.154243, 0.208017] | 319 | 319 |
| LocalPlus — historical model axis | evaluated | 0.171550 | [0.148580, 0.200863] | 319 | 319 |
| DeepGO-SE — historical model axis | evaluated | 0.131391 | [0.111653, 0.156202] | 319 | 319 |
| Current nonexperimental annotations | evaluated | 0.146169 | [0.120002, 0.175285] | 319 | 319 |
| Context stacker — zero-layer MLP | evaluated | 0.194713 | [0.164379, 0.229618] | 319 | 319 |
| Context stacker — eight-layer GCN | evaluated | 0.182759 | [0.156601, 0.212762] | 319 | 319 |
| Context GCN — evidence/relation features | evaluated | 0.210093 | [0.176059, 0.248040] | 319 | 319 |
| LocalPlus — matched training-label update | evaluated | 0.175187 | [0.151335, 0.203451] | 319 | 319 |
| Updated LocalPlus — same soft processing | evaluated | 0.175187 | [0.151335, 0.203451] | 319 | 319 |
| Training-label frequency only | evaluated | 0.107277 | [0.091352, 0.127559] | 319 | 319 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.182771 | [0.158724, 0.211901] | 319 | 319 |
| Development-selected context stacker | evaluated | 0.210093 | [0.176059, 0.248040] | 319 | 319 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.190092 | [0.159439, 0.223095] | 319 | 319 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.146169 | [0.120002, 0.175285] | 319 | 319 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.196834 | [0.164471, 0.233979] | 319 | 319 |
| LocalPlus — retained and current curated seed union | evaluated | 0.176917 | [0.152776, 0.205417] | 319 | 319 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.133967 | [0.109607, 0.160539] | 319 | 319 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.025285 | [-0.006521, +0.055630] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.065443 | [+0.039214, +0.093096] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.025285 | [-0.006521, +0.055630] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.064744 | [+0.037287, +0.092219] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.031877 | [+0.003421, +0.061582] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.018805 | [-0.011118, +0.048789] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.025285 | [-0.006521, +0.055630] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.065443 | [+0.039214, +0.093096] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.050665 | [+0.032694, +0.070656] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | +0.002122 | [-0.017051, +0.022153] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.014075 | [-0.002599, +0.032167] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | -0.013259 | [-0.027366, +0.000478] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.021648 | [-0.009569, +0.052683] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.021648 | [-0.009569, +0.052683] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.089557 | [+0.052852, +0.126781] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.014063 | [-0.017468, +0.045732] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | -0.013259 | [-0.027366, +0.000478] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.006742 | [-0.005569, +0.020520] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.050665 | [+0.032694, +0.070656] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.019917 | [-0.010996, +0.051105] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.062867 | [+0.043573, +0.085024] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.005367 | [-0.000302, +0.009131] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.001730 | [-0.002417, +0.005669] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.005854 | [-0.011054, -0.001650] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.033176 | [-0.064401, -0.003180] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | +0.030748 | [+0.000898, +0.060983] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | -0.037583 | [-0.069361, -0.010708] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | -0.041220 | [-0.071985, -0.013373] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.048804 | [-0.080552, -0.020021] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.076126 | [-0.100427, -0.054633] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | -0.012202 | [-0.019576, -0.003953] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.042950 | [+0.015083, +0.073253] |

### fixed_T0 · NK · Biological process

Full native protein frame: 8; proteins with residual positive labels: 8.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.214925 | [0.161939, 0.328364] | 8 | 8 |
| DeepGO-SE — sequence model | evaluated | 0.301205 | [0.210021, 0.419516] | 8 | 8 |
| LocalPlus — same soft processing | evaluated | 0.214925 | [0.161939, 0.328364] | 8 | 8 |
| DeepGO-SE — same soft processing | evaluated | 0.303867 | [0.210086, 0.419582] | 8 | 8 |
| Fixed 50/50 combination | evaluated | 0.310249 | [0.213439, 0.422604] | 8 | 8 |
| Development-selected global weight | evaluated | 0.264249 | [0.183993, 0.398342] | 8 | 8 |
| LocalPlus — historical model axis | evaluated | 0.214925 | [0.161939, 0.328364] | 8 | 8 |
| DeepGO-SE — historical model axis | evaluated | 0.301205 | [0.210021, 0.419516] | 8 | 8 |
| Current nonexperimental annotations | evaluated | 0.223108 | [0.022099, 0.391931] | 8 | 8 |
| Context stacker — zero-layer MLP | evaluated | 0.318339 | [0.176701, 0.434045] | 8 | 8 |
| Context stacker — eight-layer GCN | evaluated | 0.284790 | [0.189186, 0.391833] | 8 | 8 |
| Context GCN — evidence/relation features | evaluated | 0.312727 | [0.185046, 0.431377] | 8 | 8 |
| LocalPlus — matched training-label update | evaluated | 0.227129 | [0.161486, 0.321855] | 8 | 8 |
| Updated LocalPlus — same soft processing | evaluated | 0.227129 | [0.161486, 0.321855] | 8 | 8 |
| Training-label frequency only | evaluated | 0.219697 | [0.158935, 0.324528] | 8 | 8 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.238213 | [0.170300, 0.358879] | 8 | 8 |
| Development-selected context stacker | evaluated | 0.312727 | [0.185046, 0.431377] | 8 | 8 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.316547 | [0.182589, 0.441316] | 8 | 8 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.223108 | [0.022099, 0.391931] | 8 | 8 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.317647 | [0.174302, 0.457685] | 8 | 8 |
| LocalPlus — retained and current curated seed union | evaluated | 0.234940 | [0.166638, 0.349754] | 8 | 8 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.223108 | [0.022099, 0.391931] | 8 | 8 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.102722 | [-0.021551, +0.177006] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.016442 | [-0.119390, +0.105082] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.102722 | [-0.021551, +0.177006] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.013780 | [-0.118672, +0.096010] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.007398 | [-0.119878, +0.082738] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.053398 | [-0.067982, +0.122677] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.102722 | [-0.021551, +0.177006] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.016442 | [-0.119390, +0.105082] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.094539 | [+0.022237, +0.274766] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | -0.000692 | [-0.025672, +0.043100] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.032857 | [-0.032497, +0.080977] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | +0.004920 | [-0.014613, +0.036571] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.090518 | [-0.019980, +0.174311] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.090518 | [-0.019980, +0.174311] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.097950 | [-0.037465, +0.200862] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.079434 | [-0.035692, +0.157106] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | +0.004920 | [-0.014613, +0.036571] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.001100 | [-0.011766, +0.029334] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.094539 | [+0.022237, +0.274766] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.082707 | [-0.034075, +0.161723] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.094539 | [+0.022237, +0.274766] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.020014 | [-0.008880, +0.037416] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.007810 | [-0.006189, +0.035246] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.003274 | [-0.016667, +0.020148] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.077788 | [-0.149799, +0.026648] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | +0.011832 | [-0.098913, +0.205974] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | +0.008182 | [-0.192295, +0.112679] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | -0.004022 | [-0.194552, +0.109478] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.015106 | [-0.200448, +0.087826] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.089620 | [-0.264186, -0.011599] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | +0.000000 | [+0.000000, +0.000000] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.011832 | [-0.098913, +0.205974] |

### fixed_T0 · LK · Biological process

Full native protein frame: 59; proteins with residual positive labels: 59.

| Method | Status | Ordinary micro-Fmax | Copied score 95% interval | Raw rows | Residual-positive proteins |
|---|---|---|---|---|---|
| LocalPlus — retained annotations | evaluated | 0.340171 | [0.296156, 0.399022] | 59 | 59 |
| DeepGO-SE — sequence model | evaluated | 0.313185 | [0.275388, 0.361881] | 59 | 59 |
| LocalPlus — same soft processing | evaluated | 0.340171 | [0.296156, 0.399022] | 59 | 59 |
| DeepGO-SE — same soft processing | evaluated | 0.315253 | [0.276919, 0.367235] | 59 | 59 |
| Fixed 50/50 combination | evaluated | 0.351687 | [0.308298, 0.404309] | 59 | 59 |
| Development-selected global weight | evaluated | 0.354776 | [0.310359, 0.414691] | 59 | 59 |
| LocalPlus — historical model axis | evaluated | 0.340171 | [0.296156, 0.399022] | 59 | 59 |
| DeepGO-SE — historical model axis | evaluated | 0.313185 | [0.275388, 0.361881] | 59 | 59 |
| Current nonexperimental annotations | evaluated | 0.360575 | [0.274069, 0.449685] | 59 | 59 |
| Context stacker — zero-layer MLP | evaluated | 0.394366 | [0.333011, 0.463488] | 59 | 59 |
| Context stacker — eight-layer GCN | evaluated | 0.389590 | [0.339635, 0.457666] | 59 | 59 |
| Context GCN — evidence/relation features | evaluated | 0.388728 | [0.335618, 0.456185] | 59 | 59 |
| LocalPlus — matched training-label update | evaluated | 0.339415 | [0.298755, 0.401472] | 59 | 59 |
| Updated LocalPlus — same soft processing | evaluated | 0.339415 | [0.298755, 0.401472] | 59 | 59 |
| Training-label frequency only | evaluated | 0.228840 | [0.198604, 0.266817] | 59 | 59 |
| LocalPlus — complete current-T0 curated seeds | evaluated | 0.359870 | [0.316032, 0.426140] | 59 | 59 |
| Development-selected context stacker | evaluated | 0.388728 | [0.335618, 0.456185] | 59 | 59 |
| Selected stacker + legal T0 annotation prior | evaluated | 0.388460 | [0.333984, 0.455513] | 59 | 59 |
| Matched annotation-only prior at author Float32(0.99) | evaluated | 0.360575 | [0.274069, 0.449685] | 59 | 59 |
| Context GCN — current-T0 positive-union refit | evaluated | 0.395948 | [0.340399, 0.466836] | 59 | 59 |
| LocalPlus — retained and current curated seed union | evaluated | 0.348803 | [0.308713, 0.417425] | 59 | 59 |
| Direct prior — current nonexperimental + retained curated annotations | evaluated | 0.345116 | [0.262814, 0.435807] | 59 | 59 |

| Candidate | Comparator | Observed Fmax difference | Copied paired 95% interval |
|---|---|---|---|
| Context GCN — current-T0 positive-union refit | LocalPlus — retained annotations | +0.055777 | [+0.004602, +0.111748] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — sequence model | +0.082764 | [+0.035959, +0.132179] |
| Context GCN — current-T0 positive-union refit | LocalPlus — same soft processing | +0.055777 | [+0.004602, +0.111748] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — same soft processing | +0.080696 | [+0.035148, +0.128656] |
| Context GCN — current-T0 positive-union refit | Fixed 50/50 combination | +0.044261 | [+0.002832, +0.090789] |
| Context GCN — current-T0 positive-union refit | Development-selected global weight | +0.041173 | [-0.003751, +0.091291] |
| Context GCN — current-T0 positive-union refit | LocalPlus — historical model axis | +0.055777 | [+0.004602, +0.111748] |
| Context GCN — current-T0 positive-union refit | DeepGO-SE — historical model axis | +0.082764 | [+0.035959, +0.132179] |
| Context GCN — current-T0 positive-union refit | Current nonexperimental annotations | +0.035374 | [-0.005456, +0.087124] |
| Context GCN — current-T0 positive-union refit | Context stacker — zero-layer MLP | +0.001582 | [-0.027838, +0.031940] |
| Context GCN — current-T0 positive-union refit | Context stacker — eight-layer GCN | +0.006359 | [-0.022099, +0.031533] |
| Context GCN — current-T0 positive-union refit | Context GCN — evidence/relation features | +0.007221 | [-0.013904, +0.029063] |
| Context GCN — current-T0 positive-union refit | LocalPlus — matched training-label update | +0.056534 | [+0.002937, +0.111480] |
| Context GCN — current-T0 positive-union refit | Updated LocalPlus — same soft processing | +0.056534 | [+0.002937, +0.111480] |
| Context GCN — current-T0 positive-union refit | Training-label frequency only | +0.167108 | [+0.096577, +0.248900] |
| Context GCN — current-T0 positive-union refit | LocalPlus — complete current-T0 curated seeds | +0.036078 | [-0.017714, +0.087332] |
| Context GCN — current-T0 positive-union refit | Development-selected context stacker | +0.007221 | [-0.013904, +0.029063] |
| Context GCN — current-T0 positive-union refit | Selected stacker + legal T0 annotation prior | +0.007488 | [-0.011605, +0.026046] |
| Context GCN — current-T0 positive-union refit | Matched annotation-only prior at author Float32(0.99) | +0.035374 | [-0.005456, +0.087124] |
| Context GCN — current-T0 positive-union refit | LocalPlus — retained and current curated seed union | +0.047145 | [-0.010980, +0.099434] |
| Context GCN — current-T0 positive-union refit | Direct prior — current nonexperimental + retained curated annotations | +0.050832 | [+0.007474, +0.103313] |
| LocalPlus — retained and current curated seed union | LocalPlus — retained annotations | +0.008632 | [-0.003016, +0.028063] |
| LocalPlus — retained and current curated seed union | LocalPlus — matched training-label update | +0.009389 | [-0.002227, +0.025221] |
| LocalPlus — retained and current curated seed union | LocalPlus — complete current-T0 curated seeds | -0.011067 | [-0.019487, +0.005386] |
| LocalPlus — retained and current curated seed union | Development-selected context stacker | -0.039925 | [-0.089521, +0.012667] |
| LocalPlus — retained and current curated seed union | Current nonexperimental annotations | -0.011771 | [-0.082831, +0.077688] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — retained annotations | +0.004945 | [-0.078054, +0.080307] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — matched training-label update | +0.005702 | [-0.080226, +0.078167] |
| Direct prior — current nonexperimental + retained curated annotations | LocalPlus — complete current-T0 curated seeds | -0.014754 | [-0.098461, +0.057252] |
| Direct prior — current nonexperimental + retained curated annotations | Development-selected context stacker | -0.043611 | [-0.101859, -0.000813] |
| Direct prior — current nonexperimental + retained curated annotations | Current nonexperimental annotations | -0.015458 | [-0.047509, +0.000000] |
| LocalPlus — retained and current curated seed union | Direct prior — current nonexperimental + retained curated annotations | +0.003687 | [-0.068064, +0.092939] |

## Method and limits

- The model is one eight-layer context GCN with the same 40 source-derived evidence/relation channels and fixed January2023 output ontology. The current source contains 867 heads receiving new fitting assignments; only 64 gain their first positive fitting label. These are not 867 new output classes.

- Targets retain the complete historical fitting repertoire and union only the source-admitted direct current-T0 curated positives. Missing current annotations are not used as negative evidence or as instructions to remove historical positives. The dated T0 source was generated April10,2026; native Experimental/IC/TAS admission and identifier/ontology handling are unchanged.

- The full 4,040-protein fitting frame supplies updated priors before root-positive filtering. Both fitting and final parent features use those same priors. Fitting GOA context is updated to T0; the already sealed final T0 context and both raw parent forecasts are reused.

- No current validation metric or outcome-based checkpoint selection is computed. Three SWA epoch positions are fixed from the original pre-opening run. Transferring that fixed schedule to this source update is a disclosed development adaptation, not a validated new training recipe.

- The LocalPlus control unions retained historical seeds, the matched fitting update, the candidate’s exact augmented4,040-protein positive target repertoire with its fixed-old-ontology ancestors, and complete current-T0 curated seeds on the unchanged graph and native scorer. It does not seed nonexperimental annotations. The GCN additionally uses the DeepGO-SE parent and 40 nonexperimental context channels. This is a stronger annotation control; the comparison does not isolate learning as the sole source of any difference. The direct source-union prior combines current nonexperimental and retained curated memberships at score1 on their complete literal vocabulary.

- Every earlier BP method remains visible, including the earlier fixed 0.99 annotation-prior follow-up. All stored contrasts are shown; observed point subtraction is display arithmetic, and no interval, threshold, winner or new success gate is selected by this renderer.

- Later-snapshot curator annotations assess annotation recovery, not independent experiments, publication novelty or the percentage of biologically correct Pharos edges. An unmatched prediction is not an established biological falsehood. Exact source NOT/positive overlaps and incomplete context remain documented source limitations.

- The reference had already been consumed when this refit was planned. Favorable or unfavorable results are development evidence and require independent confirmation. The original frozen comparison, its success gates and previous publication remain unchanged. No automatic graph pruning or application-default change is made.

Published implementation: [ProtBoost/CAFA6 author code](https://github.com/btbpanda/CAFA6-updates).
