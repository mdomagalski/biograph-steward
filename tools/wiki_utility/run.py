#!/usr/bin/env python3
"""Fixed CPU native R-GCN replay adapted from the existing Reactome runner.

Only graph/arm validation and the reporting namespace differ. Native factory,
training loop, losses, typed sampler, exact filters, schedule, model and pairing
controls are reused. No outcomes are read here. This is a consumed-reference
retrospective development comparison; no model or GPU service is involved.
"""
from collections import defaultdict
from copy import deepcopy
import argparse, gc, hashlib, json, math, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from tools.wiki_utility.prepare import ARMS, SEEDS, RELATION, verify, need, IMPLEMENTATION
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from scripts.run_reactome_context import (native_factory, adjacency, parameter_hash, hash_tensor,
    runtime_binding, FINGERPRINTS, MODEL, TRAINING)
from scripts.run_inmc_comparison import GENE

def _write(path,value):write_json(path,value)

def schedule(n,*,mode):
    need(mode in {'resource_check','full'},'unknown run mode')
    need(n==99394,'shared supervision must remain the original 99,394 directed HuRI triples')
    epochs=1 if mode=='resource_check' else 20
    seeds=[17] if mode=='resource_check' else SEEDS
    return {'epochs':epochs,'batch_size':4096,'seeds':seeds,
        'updates_per_arm_seed':epochs*math.ceil(n/4096),'runs':len(ARMS)*len(seeds),
        'total_updates':len(ARMS)*len(seeds)*epochs*math.ceil(n/4096)}

def validate_complete_runs(results,settings):
    need(len(results)==len(ARMS)*len(settings['seeds']),'duplicate or missing run receipts')
    need({(r['arm'],r['seed']) for r in results}=={(a,s) for a in ARMS for s in settings['seeds']},'incomplete fixed arms')
    for seed in settings['seeds']:
        paired=[r for r in results if r['seed']==seed]
        for field in FINGERPRINTS:
            need(len({r[field] for r in paired})==1,'paired training fingerprint differs: '+field)
        need(len({r['parameter_count'] for r in paired})==1,'parameter budgets differ')
        need(all(r['optimizer_steps']==settings['updates_per_arm_seed'] and r['optimizer_state_steps']==[settings['updates_per_arm_seed']]
             and r['epochs_completed']==settings['epochs'] for r in paired),'optimizer/epoch budget differs')


def message_probe(packet):
    """Use the actual frozen native adjacency, shared random parameters, no fit.

    This establishes input visibility only. Differences under random weights
    are not biological predictions, and no assay labels are accessed.
    """
    import torch
    from pykeen.models import RGCN
    ids={v:i for i,v in enumerate(packet['entities'])}
    relations={v:i for i,v in enumerate(packet['relations'])}
    embeddings={};hashes={};adjacencies={}
    for arm in ARMS:
        context=native_factory(packet['arms'][arm],ids,relations)
        model=RGCN(triples_factory=context,embedding_dim=32,num_layers=3,decomposition='bases',
            decomposition_kwargs={'num_bases':4},activation='relu',edge_dropout=0.0,
            self_loop_dropout=0.0,random_seed=17,loss='softplus').to('cpu')
        model.entity_representations[0].edge_dropout=None
        hashes[arm]=parameter_hash(model)
        need(torch.equal(adjacency(model),context.mapped_triples),'probe native adjacency differs')
        adjacencies[arm]=digest(adjacency(model).tolist())
        model.eval()
        with torch.inference_mode():embeddings[arm]=model.entity_representations[0](indices=None).detach().cpu()
        del model,context
    need(len(set(hashes.values()))==1,'probe parameters differ')
    need(len(set(adjacencies.values()))==len(ARMS),'probe arm adjacency is unchanged')
    result={}
    for arm in ARMS[1:]:
        delta=(embeddings[arm]-embeddings[ARMS[0]]).abs().amax(dim=1)
        result[arm]={'changed_entities':int((delta>0).sum()),'maximum_embedding_delta':float(delta.max()),
            'candidate_pairs_with_changed_endpoint':sum(any(float(delta[ids[g]])>0 for g in r['original_genes'])
                                                     for r in packet['candidates']),
            'candidate_endpoint_maximum_delta':max(float(delta[ids[g]]) for r in packet['candidates'] for g in r['original_genes'])}
    need(result[ARMS[1]]['candidate_pairs_with_changed_endpoint']>0,'qualified input has no native candidate message influence')
    return {'shared_parameter_sha256':next(iter(hashes.values())),'adjacency_sha256':adjacencies,
        'qualified_versus_normalized_and_controls':result,'fit_performed':False,'outcomes_loaded':False,
        'biological_utility_established':False,'message_passing_layers':3,
        'native_bidirectional_messages_are_not_symmetric_biological_edges':True}

def fit(packet, output, *, execution, mode):
    """The one native training path used by invented controls and fixed real runs."""
    import torch
    from pykeen.models import RGCN
    from pykeen.predict import predict_triples
    from pykeen.sampling import PseudoTypedNegativeSampler
    from pykeen.sampling.filtering import PythonSetFilterer
    from pykeen.training import SLCWATrainingLoop, TrainingCallback
    from pykeen.utils import set_random_seed

    torch.set_num_threads(1)
    device = execution["device"]
    settings = schedule(len(packet["supervision"]), mode=mode)
    entity_ids = {name: i for i, name in enumerate(packet["entities"])}
    relation_ids = {name: i for i, name in enumerate(packet["relations"])}
    factory = lambda rows: native_factory(rows, entity_ids, relation_ids)
    def mapped(rows):
        return torch.tensor([[entity_ids[a], relation_ids[r], entity_ids[b]] for a, r, b in rows], dtype=torch.long)
    supervision = factory(packet["supervision"])
    blocked_rows = set(packet["supervision"]) | {(b, r, a) for a, r, b in packet["supervision"]}
    for a, b in packet["masked_gene_pairs"]:
        blocked_rows.update(((a, "interacts", b), (b, "interacts", a)))
    blocked = mapped(sorted(blocked_rows))
    blocked_set = set(map(tuple, blocked.tolist()))
    positive_set = set(map(tuple, supervision.mapped_triples.tolist()))
    genes = {index for name, index in entity_ids.items() if GENE.fullmatch(name)}
    filterer = PythonSetFilterer(mapped_triples=blocked)
    if filterer(negative_batch=blocked).any():
        raise ValueError("Native exact filter did not block supervision and both held-out orientations.")

    class Observe(TrainingCallback):
        def __init__(self):
            super().__init__()
            self.steps, self.epochs, self.proposals, self.filtered = 0, 0, 0, 0
            self.initial = None
            self.hashes = {name: hashlib.sha256() for name in FINGERPRINTS[1:]}
            self.seen = set()

        def pre_batch(self, **unused):
            # train() resets parameters: construction-time fingerprints do not prove pairing.
            if self.initial is None:
                self.initial = parameter_hash(self.model)

        def post_batch(self, epoch, batch, **unused):
            positives = batch["positives"].detach().cpu()
            rows = set(map(tuple, positives.tolist()))
            if not rows <= positive_set or self.seen & rows or len(rows) != len(positives):
                raise ValueError("Native minibatch omits/duplicates supervision or contains context positives.")
            self.seen.update(rows)
            negatives = batch["negatives"].detach().cpu()
            mask = batch.get("masks")
            if mask is None or tuple(negatives.shape) != (len(positives), 16, 3):
                raise ValueError("Native sampler did not produce exactly 16 filtered proposals per positive.")
            mask = mask.detach().cpu()
            if tuple(mask.shape) != (len(positives), 16) or not torch.equal(filterer(negative_batch=negatives), mask):
                raise ValueError("Native negative filter mask differs from exact identity exclusions.")
            for a, r, b in negatives.reshape(-1, 3).tolist():
                if a not in genes or b not in genes or r != relation_ids["interacts"]:
                    raise ValueError("Typed proposals contain context entities or relations.")
            if blocked_set.intersection(map(tuple, negatives[mask].tolist())):
                raise ValueError("Accepted negative violates candidate/development/equivalence exclusions.")
            self.steps += 1
            self.proposals += mask.numel()
            self.filtered += int((~mask).sum())
            for name, value in (("positive_batch_sha256", positives), ("negative_proposal_sha256", negatives),
                                ("negative_filter_mask_sha256", mask), ("accepted_negative_sha256", negatives[mask])):
                self.hashes[name].update(str(epoch).encode())
                hash_tensor(self.hashes[name], value)

        def post_epoch(self, **unused):
            if self.seen != positive_set:
                raise ValueError("Native epoch did not visit every supervision triple exactly once.")
            self.epochs += 1
            self.seen.clear()

    results = []
    for seed in settings["seeds"]:
        for arm in ARMS:
            context = factory(packet["arms"][arm])
            model = RGCN(triples_factory=context, embedding_dim=32, num_layers=3, decomposition="bases",
                    decomposition_kwargs={"num_bases": 4}, activation="relu", edge_dropout=0.0,
                    self_loop_dropout=0.0, random_seed=seed, loss="softplus").to(device)
            rep = model.entity_representations[0]
            if (type(model.loss).__name__ != "SoftplusLoss" or type(model.interaction).__name__ != "DistMultInteraction"
                    or len(rep.layers) != 3 or any(layer.fwd.relation_representations.num_bases != 4 for layer in rep.layers)):
                raise ValueError("Native model resolved a different loss, decoder, layer or basis profile.")
            if any(layer.dropout.p != 0.0 for layer in rep.layers):
                raise ValueError("Native self-loop dropout violates the zero-dropout policy.")
            # Supported native disabled branch avoids adjacency-size-dependent RNG at p=0.
            rep.edge_dropout = None
            if not torch.equal(adjacency(model), context.mapped_triples):
                raise ValueError("Native R-GCN adjacency differs from the selected context arm.")
            loop = SLCWATrainingLoop(model=model, triples_factory=supervision, optimizer="Adam",
                    optimizer_kwargs={"lr": 0.001}, automatic_memory_optimization=False,
                    negative_sampler=PseudoTypedNegativeSampler,
                    negative_sampler_kwargs={"num_negs_per_pos": 16, "filterer": filterer})
            observer = Observe()
            set_random_seed(seed)
            if device == "cuda:0":
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
            started = time.perf_counter()
            losses = loop.train(triples_factory=supervision, num_epochs=settings["epochs"],
                    batch_size=settings["batch_size"], sampler=None, use_tqdm=False, num_workers=0,
                    pin_memory=False, drop_last=False, checkpoint_directory=output / "checkpoints" / f"{arm}_{seed}",
                    callbacks=observer)
            if device == "cuda:0":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            if losses is None or not all(math.isfinite(float(v)) for v in losses):
                raise ValueError("Native training did not finish with finite losses.")
            optimizer_steps = sorted({int(s["step"].item()) for s in loop.optimizer.state.values() if "step" in s})
            if type(loop.optimizer).__name__ != "Adam" or any(group["lr"] != 0.001 for group in loop.optimizer.param_groups):
                raise ValueError("Native optimizer differs from the selected Adam learning rate.")
            if rep.enriched_embeddings is not None or not torch.equal(adjacency(model), context.mapped_triples):
                raise ValueError("Training failed native cache invalidation or changed graph adjacency.")
            result = {"arm": arm, "seed": seed, "status": "passed", "optimizer_steps": observer.steps,
                      "optimizer_state_steps": optimizer_steps, "epochs_completed": observer.epochs,
                      "initial_parameters_sha256": observer.initial,
                      **{name: value.hexdigest() for name, value in observer.hashes.items()},
                      "negative_proposals": observer.proposals, "negative_proposals_filtered": observer.filtered,
                      "losses": [float(v) for v in losses], "adjacency_triples": context.num_triples,
                      "adjacency_sha256": digest(adjacency(model).tolist()), "supervision_triples": supervision.num_triples,
                      "parameter_count": sum(p.numel() for p in model.parameters()), "training_seconds": elapsed,
                      "training_invalidated_cache": True,
                      "max_cuda_memory_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda:0" else None}
            # Resource mode does not even build development or candidate query tensors.
            if mode != "resource_check":
                prediction_rows = [("development", row) for row in packet["development"]]
                prediction_rows += [("candidate", row) for row in packet["candidates"]]
                query_rows = [(a, "interacts", b) for _, row in prediction_rows
                              for a, b in (row["original_genes"], list(reversed(row["original_genes"])))]
                queries = mapped(query_rows)
                with torch.inference_mode():
                    predictions = predict_triples(model=model, triples=queries, batch_size=1024)
                if not torch.equal(predictions.result.cpu(), queries) or not torch.isfinite(predictions.scores).all():
                    raise ValueError("Native query identity/order or finite prediction completeness differs.")
                scores = predictions.scores.detach().cpu().tolist()
                rows = []
                for index, (partition, row) in enumerate(prediction_rows):
                    forward, reverse = scores[2 * index:2 * index + 2]
                    if not math.isclose(forward, reverse, abs_tol=1e-5, rel_tol=1e-5):
                        raise ValueError("Native DistMult decoder violates paired orientation symmetry.")
                    rows.append({**row, "partition": partition, "forward": forward, "reverse": reverse,
                                 "score": (forward + reverse) / 2})
                name = f"{arm}_{seed}_scores.json"
                _write(output / name, rows)
                result.update(scores_file=name, score_rows=len(rows), query_sha256=digest(query_rows))
                if not torch.equal(adjacency(model), context.mapped_triples):
                    raise ValueError("Prediction inserted query edges into adjacency.")
            if mode == "full":
                name = f"{arm}_{seed}_state.pt"
                torch.save(model.state_dict(), output / name)
                result["checkpoint"] = name
            results.append(result)
            _write(output / f"{arm}_{seed}_receipt.json", result)
            del model, loop, observer, context, rep
            gc.collect()
            if device == "cuda:0":
                torch.cuda.empty_cache()
    validate_complete_runs(results, settings)
    return results, settings


def run(packet_path,out,*,resource=False):
    report,packet=verify(packet_path)
    output=new_output(out,packet_path)
    os.environ.setdefault('PYSTOW_HOME',str(output/'cache'))
    os.environ.setdefault('PYKEEN_HOME',str(output/'cache'/'pykeen'))
    # PyKEEN imports PyStow, which initializes its cache during the runtime
    # source audit. Configure the documented writable cache before that import.
    execution=runtime_binding('cpu')
    mode='resource_check' if resource else 'full'
    pins={p:sha(ROOT/p) for p in IMPLEMENTATION}
    probe=message_probe(packet)
    write_json(output/'native_message_probe.json',probe)
    results,settings=fit(packet,output,execution=execution,mode=mode)
    need(verify(packet_path)[0]==report,'frozen packet changed during run')
    need({p:sha(ROOT/p) for p in IMPLEMENTATION}==pins,'implementation changed during run')
    result={'format':'biograph-steward.wiki-utility-native-development-run.v1','created_at':utcnow(),
        'packet_report_sha256':sha(Path(packet_path)/'report.json'),'packet_content_sha256':report['content_sha256'],
        'execution':execution,'mode':mode,'profile':{'model':MODEL,'training':TRAINING},'schedule':settings,
        'results':results,'native_message_probe':probe,'implementation_sha256':pins,'candidate_outcomes_loaded':False,
        'retrospective_consumed_reference':True,'biological_accuracy_claimed':False,'automatic_graph_changes':False,
        'files':{p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}}
    result['content_sha256']=digest(result);write_json(output/'report.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--resource',action='store_true')
    a=p.parse_args();print(run(a.packet,a.out,resource=a.resource)['content_sha256'])
if __name__=='__main__':main()
