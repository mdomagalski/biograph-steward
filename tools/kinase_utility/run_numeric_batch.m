% Pure numeric transport around unchanged author RoKAI functions.
% Fixed container API: /input/<name>.mat -> /output/<name>.mat.
% No measurement identifiers, expected targets, labels or metadata are read.
args = argv();
assert(numel(args) == 2, 'Supply staged numeric input and output MAT paths.');
input_file = args{1};
output_file = args{2};
[input_directory, input_name, input_extension] = fileparts(input_file);
[output_directory, output_name, output_extension] = fileparts(output_file);
assert(strcmp(input_directory, '/input') && strcmp(input_extension, '.mat') && ...
       !isempty(regexp(input_name, '^[A-Za-z0-9_-]+$', 'once')), 'Input must be a staged numeric MAT file.');
assert(strcmp(output_directory, '/output') && strcmp(output_extension, '.mat') && ...
       !isempty(regexp(output_name, '^[A-Za-z0-9_-]+$', 'once')), 'Output must be a staged numeric MAT file.');
assert(exist(output_file, 'file') == 0, 'Refusing to overwrite a numeric output.');

required = {'X'; 'Wkin2site'; 'Wsite2site'; 'W_unpruned'; 'W_native'; 'W_primary'; 'W_ne'};
inventory = whos('-file', input_file);
assert(isequal(sort({inventory.name}'), sort(required)), 'Unexpected or missing numeric input variables.');
assert(all(strcmp({inventory.class}, 'double')), 'All staged arrays must be float64/double.');
data = load(input_file);
X = data.X;
Wkin2site = data.Wkin2site;
Wsite2site = data.Wsite2site;
assert(isa(X, 'double') && ismatrix(X) && isreal(X) && !issparse(X) && ...
       rows(X) >= 1 && columns(X) >= 1 && !any(isinf(X(:))), 'Invalid numeric measurement matrix.');
nSite = rows(X);
nCondition = columns(X);
assert(isa(Wkin2site, 'double') && ismatrix(Wkin2site) && isreal(Wkin2site) && ...
       rows(Wkin2site) >= 1 && columns(Wkin2site) == nSite, 'Invalid KS dimensions or type.');
assert(all(isfinite(nonzeros(Wkin2site))) && all(nonzeros(Wkin2site) == 1), 'KS must be binary positive incidence.');
assert(all(sum(Wkin2site, 2) >= 1), 'Each source enzyme requires at least one KS site.');
nEnzyme = rows(Wkin2site);
assert(isa(Wsite2site, 'double') && issparse(Wsite2site) && isreal(Wsite2site) && ...
       isequal(size(Wsite2site), [nSite nSite]) && nnz(Wsite2site) == 0, 'Site graph must be sparse zero.');
for name = {'W_unpruned', 'W_native', 'W_primary', 'W_ne'}
    W = data.(name{1});
    assert(isa(W, 'double') && ismatrix(W) && isreal(W) && ...
           isequal(size(W), [nEnzyme nEnzyme]), 'Invalid PPI dimensions or type.');
    weights = nonzeros(W);
    assert(all(isfinite(weights)) && all(weights >= 0) && all(weights <= 1), 'PPI weights require native normalized units [0,1].');
    assert(nnz(W - W') == 0 && nnz(diag(W)) == 0, 'PPI must be exactly symmetric with zero diagonal.');
end

addpath(fullfile(fileparts(mfilename('fullpath')), 'src', 'rokai'));
fprintf('octave_version=%s\nnSite=%d\nnEnzyme=%d\nnCondition=%d\n', ...
        OCTAVE_VERSION, nSite, nEnzyme, nCondition);
timer = tic();
A_raw_mean = rokai_inference(X, Wkin2site, 'mean');
fprintf('seconds_raw_mean=%.17g\n', toc(timer));
timer = tic();
A_raw_zscore = rokai_inference(X, Wkin2site, 'zscore');
fprintf('seconds_raw_zscore=%.17g\n', toc(timer));

% All propagation calls retain the same author defaults and fixed KS/site data.
% PPI inputs are already normalized: do not call rokai_networks or rescale them.
timer = tic();
refined = rokai_core(X, Wkin2site, sparse(nEnzyme, nEnzyme), Wsite2site);
A_rokai_ks_only_zscore = rokai_inference(refined, Wkin2site, 'zscore');
fprintf('seconds_rokai_ks_only_zscore=%.17g\n', toc(timer));
timer = tic();
refined = rokai_core(X, Wkin2site, data.W_unpruned, Wsite2site);
A_rokai_unpruned_zscore = rokai_inference(refined, Wkin2site, 'zscore');
fprintf('seconds_rokai_unpruned_zscore=%.17g\n', toc(timer));
timer = tic();
refined = rokai_core(X, Wkin2site, data.W_native, Wsite2site);
A_rokai_native_zscore = rokai_inference(refined, Wkin2site, 'zscore');
fprintf('seconds_rokai_native_zscore=%.17g\n', toc(timer));
timer = tic();
refined = rokai_core(X, Wkin2site, data.W_primary, Wsite2site);
A_rokai_primary_zscore = rokai_inference(refined, Wkin2site, 'zscore');
fprintf('seconds_rokai_primary_zscore=%.17g\n', toc(timer));
timer = tic();
refined = rokai_core(X, Wkin2site, data.W_ne, Wsite2site);
A_rokai_ne_zscore = rokai_inference(refined, Wkin2site, 'zscore');
fprintf('seconds_rokai_ne_zscore=%.17g\n', toc(timer));
outputs = {A_raw_mean, A_raw_zscore, A_rokai_ks_only_zscore, A_rokai_unpruned_zscore, ...
           A_rokai_native_zscore, A_rokai_primary_zscore, A_rokai_ne_zscore};
for i = 1:numel(outputs)
    assert(isa(outputs{i}, 'double') && isreal(outputs{i}) && ...
           isequal(size(outputs{i}), [nEnzyme nCondition]), 'Unexpected activity output shape.');
end
save('-mat7-binary', output_file, 'A_raw_mean', 'A_raw_zscore', ...
     'A_rokai_ks_only_zscore', 'A_rokai_unpruned_zscore', 'A_rokai_native_zscore', ...
     'A_rokai_primary_zscore', 'A_rokai_ne_zscore');
fprintf('numeric_batch=PASS\n');
