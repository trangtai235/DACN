"""Paired ID export. References are read only after inference, never by retrieval/policies."""
import random
from collections import Counter
from experiments.models import ReferenceLabel
from experiments.training import metrics
from .adaptation import checksum, schema_labels


def comparison(batches, bootstrap=False):
    if not batches: raise ValueError('Chọn ít nhất một lượt dự đoán.')
    if len({b.schema.sha256 for b in batches}) != 1: raise ValueError('Chỉ so các lượt cùng schema bất biến.')
    maps = [{(p.comment_id, p.text_hash): p for p in b.pairs.select_related('comment', 'local_prediction', 'api_prediction')} for b in batches]
    common = sorted(set.intersection(*(set(m) for m in maps)))
    keys = [l['key'] for l in schema_labels(batches[0].schema)]
    refs = dict(ReferenceLabel.objects.filter(comment__project=batches[0].project).values_list('comment_id', 'label'))
    conditions = []; audit_rows = []
    for batch, pairs in zip(batches, maps):
        for branch, field in [('local', 'local_prediction'), ('api', 'api_prediction')]:
            all_valid = [p for p in pairs.values() if p.branches[branch]['state'] == 'complete' and getattr(p, field + '_id')]
            subset = [pairs[k] for k in common if refs.get(k[0]) in keys and pairs[k].branches[branch]['state'] == 'complete' and getattr(pairs[k], field + '_id')]
            predictions = [getattr(p, field) for p in subset]
            row = {'run_id': batch.pk, 'branch': branch,
                'condition': 'local-only' if branch == 'local' else ('api-fewshot-retrieval' if batch.options.get('few_shot') else 'api-label-descriptions'),
                'population': len(pairs), 'valid': len(all_valid), 'coverage': len(all_valid)/max(1, len(pairs)),
                'errors': [{'comment_id': p.comment_id, 'state': p.branches[branch]['state'], 'error': p.branches[branch].get('error', '')} for p in pairs.values() if p.branches[branch]['state'] != 'complete'],
                'reference_n_on_common_ids': len(subset), 'scored_ids': [p.comment_id for p in subset],
                'metrics': metrics([keys.index(refs[p.comment_id]) for p in subset], [keys.index(v.label) for v in predictions], keys) if subset else None,
                'latency_ms': sum(getattr(p, field).latency_ms for p in all_valid),
                'tokens': sum(getattr(p, field).input_tokens + getattr(p, field).output_tokens for p in all_valid),
                'estimated_cost_usd': sum(getattr(p, field).estimated_cost_usd for p in all_valid)}
            if bootstrap:
                groups = {}
                for p in subset:
                    source = p.comment.source
                    key = 'video:' + source.external_id if source.kind == 'youtube' and source.external_id else 'source:' + str(source.pk)
                    groups.setdefault(key, []).append(p)
                if len(groups) >= 5 and len(subset) >= 20:
                    rng = random.Random(42); values = []; group_ids = sorted(groups)
                    for _ in range(200):
                        sample = [p for _ in group_ids for p in groups[rng.choice(group_ids)]]
                        values.append(metrics([keys.index(refs[p.comment_id]) for p in sample], [keys.index(getattr(p, field).label) for p in sample], keys)['macro_f1'])
                    values.sort(); row['cluster_bootstrap_macro_f1_95'] = [values[4], values[194]]
                    row['bootstrap_protocol'] = {'seed': 42, 'resamples': 200, 'clusters': len(groups), 'unit': 'source/video'}
                else: row['bootstrap_unavailable'] = 'Need at least 5 source clusters and 20 reference observations; no statistical guarantee is inferred.'
            conditions.append(row)
        for key in common:
            p = pairs[key]
            d = p.decisions.filter(status='confirmed').order_by('id').first()
            audit_rows.append({'run_id': batch.pk, 'comment_id': p.comment_id, 'text_hash': p.text_hash,
                'schema_sha256': batch.schema.sha256, 'local_prediction_id': p.local_prediction_id,
                'api_prediction_id': p.api_prediction_id, 'decision_id': d.pk if d else None,
                'decision_revision': d.revision if d else None, 'decision_label': d.label if d else None})
            if d:
                audit_rows[-1]['first_decision_active_seconds']=d.clock.get('active',0)
                audit_rows[-1]['first_decision_idle_seconds']=d.clock.get('idle',0)
    # Strict paired metrics: identical successful IDs in every available condition.
    comparable = [c for c in conditions if c['valid']]
    strict_ids = sorted(set.intersection(*(set(c['scored_ids']) for c in comparable))) if comparable else []
    for condition in conditions:
        pair_map = maps[[b.pk for b in batches].index(condition['run_id'])]
        field = 'local_prediction' if condition['branch'] == 'local' else 'api_prediction'
        selected = [pair_map[k] for k in common if k[0] in strict_ids and pair_map[k].branches[condition['branch']]['state'] == 'complete']
        condition['strict_paired_n'] = len(selected)
        condition['strict_paired_metrics'] = metrics([keys.index(refs[p.comment_id]) for p in selected], [keys.index(getattr(p, field).label) for p in selected], keys) if selected else None
    value = {'schema_sha256': batches[0].schema.sha256, 'schema': batches[0].schema.snapshot,
             'demo': any(b.options.get('demo') for b in batches), 'common_id_text_count': len(common), 'strict_paired_ids': strict_ids,
             'conditions': conditions, 'input_audit': audit_rows,
             'limitations': 'Observed coverage and operational cost only. Human collaboration outcome is a human decision, never automatic model agreement. Use budget reports for final labels/net fixes. Repeated seeds are not independent human observations.'}
    value['sha256'] = checksum(value)
    return value
