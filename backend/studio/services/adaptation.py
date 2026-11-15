"""Explicit project schema compatibility and deterministic, leakage-safe retrieval."""
import hashlib
import json
from collections import Counter
from django.db import transaction
from django.db.models import Max
from experiments.training import canonical
from experiments.models import ReferenceLabel
from studio.models import LabelSchema, FeedbackApproval, DataPartition, FeedbackDataset
from studio.services.projects import ensure, labels_for, PRESETS

PROMPT_VERSION = 'project-sentence-fewshot-v1'


def checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def text_hash(text, context=''):
    return checksum({'text': text, 'context': context})


@transaction.atomic
def current_schema(project):
    prefs = ensure(project)
    type(prefs).objects.select_for_update().get(pk=prefs.pk)
    snapshot = {'level': 'sentence_single', 'guidelines': prefs.guidelines,
                'labels': [{k: v for k, v in label.items() if k in ('key', 'name', 'description', 'exclusions', 'enabled')}
                           for label in sorted(labels_for(project, False),key=lambda row:row['key'])]}
    digest = checksum(snapshot)
    previous = project.label_schemas.order_by('-version').first()
    if previous and previous.sha256 == digest:
        return previous
    return LabelSchema.objects.create(project=project, version=(previous.version + 1 if previous else 1),
                                      sha256=digest, snapshot=snapshot)


def schema_labels(schema):
    return [row for row in schema.snapshot['labels'] if row['enabled']]


def compatibility(model, schema):
    if not model or model.state != 'ready':
        return {'state': 'needs_training', 'reason': 'Chưa có model local sẵn sàng; dùng API-only/human-only.'}
    report = json.loads(model.report)
    keys = {x['key'] for x in schema_labels(schema)}
    if set(report.get('label_keys', ['NON_TOXIC', 'TOXIC'])) != keys:
        return {'state': 'incompatible', 'reason': 'Checkpoint và schema khác bộ nhãn; không ánh xạ nhãn tùy ý.'}
    if report.get('schema_sha256'):
        ok = report['schema_sha256'] == schema.sha256
    else:
        # Legacy checkpoints only declare the original toxicity task, never arbitrary schemas.
        definitions = {x['key']: (x['name'], x['description'], x.get('exclusions', '')) for x in schema_labels(schema)}
        ok = definitions == {key: (name, description, '') for key, name, _, description in PRESETS['toxicity']}
        ok = ok and schema.snapshot['guidelines'] == ensure(schema.project)._meta.get_field('guidelines').get_default()
    return {'state': 'compatible' if ok else 'needs_evaluation',
            'reason': 'Khớp nhiệm vụ/schema.' if ok else 'Ý nghĩa/hướng dẫn schema thay đổi; cần train và đánh giá lại.'}


def eligible_feedback(project, schema):
    excluded = set(DataPartition.objects.filter(comment__project=project).exclude(role='support').values_list('comment_id', flat=True))
    excluded.update(ReferenceLabel.objects.filter(comment__project=project).values_list('comment_id', flat=True))
    # Exclude duplicates of every held-out text as well as the held-out IDs.
    held_text = {canonical(t) for t in project.comments.filter(pk__in=excluded).values_list('text', flat=True)}
    held_sources=set(project.comments.filter(pk__in=excluded).values_list('source_id',flat=True))
    held_videos=set(project.sources.filter(pk__in=held_sources,kind='youtube').exclude(external_id='').values_list('external_id',flat=True))
    rows = FeedbackApproval.objects.filter(comment__project=project, schema=schema, revoked=False).exclude(comment_id__in=excluded).select_related('decision__annotation__label', 'comment__source').order_by('id')
    result = []
    for row in rows:
        d = row.decision
        if row.source_id_snapshot in held_sources or (row.comment.source.kind=='youtube' and row.comment.source.external_id in held_videos):continue
        if d.status != 'confirmed' or d.label != row.label or row.text != row.comment.text:
            continue
        if d.revision!=row.decision_revision:continue
        if not d.annotation_id or d.annotation.status != 'submitted' or not d.annotation.label_id or d.annotation.label.key != row.label:
            continue
        if not d.history or d.history[-1].get('annotation_revision') != d.annotation.revision:
            continue
        if row.text_hash != text_hash(row.comment.text, row.comment.context) or canonical(row.text) in held_text:
            continue
        if row.comment.prediction_pairs.filter(decisions__status__in=['escalated', 'needs_context', 'undecidable']).exists():
            continue
        if row.comment.annotations.filter(status='submitted').exclude(label__key=row.label).exists():
            from studio.models import GoldAnnotation
            if not GoldAnnotation.objects.filter(comment=row.comment, label__key=row.label).exists(): continue
        result.append(row)
    unique={}; label_sets={}
    for row in result:
        unique.setdefault(canonical(row.text),row)
        label_sets.setdefault(canonical(row.text),set()).add(row.label)
    return [row for key,row in unique.items() if len(label_sets[key])==1]


def retrieve(project, schema, comment, limit=4, max_chars=2400):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    rows = [r for r in eligible_feedback(project, schema) if r.comment_id != comment.id and canonical(r.text) != canonical(comment.text)]
    if not rows:
        return []
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 4))
    matrix = vectorizer.fit_transform([r.text for r in rows] + [comment.text])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    ordered = sorted(zip(rows, scores), key=lambda value: (-value[1], value[0].pk))
    out = []; seen = set(); used = 0
    for row, score in ordered:
        key = canonical(row.text)
        if key in seen or len(row.text) > 800 or used + len(row.text) > max_chars:
            continue
        seen.add(key); used += len(row.text)
        out.append({'approval_id': row.id, 'decision_id': row.decision_id, 'decision_revision': row.decision.revision,
                    'text_hash': row.text_hash, 'text': row.text, 'label': row.label, 'score': float(score)})
        if len(out) >= limit:
            break
    return out


def readiness(project, schema):
    rows = eligible_feedback(project, schema)
    counts = Counter(r.label for r in rows)
    groups = Counter(r.source_id_snapshot for r in rows)
    return {'counts': {r['key']: counts[r['key']] for r in schema_labels(schema)}, 'sources': len(groups),
            'missing_classes': [r['key'] for r in schema_labels(schema) if not counts[r['key']]],
            'message': 'Cần ít nhất ba nguồn độc lập và đủ mọi lớp ở từng split; số lượng nhỏ không bảo đảm chất lượng.'}


@transaction.atomic
def freeze_dataset(project, schema, seed=42):
    import random
    if not 0<=seed<=4294967295:raise ValueError('Seed từ 0 đến 4294967295.')
    rows = eligible_feedback(project, schema)
    # Group duplicates AND video/source groups using connected components.
    parent = {}
    def source_key(row):
        source=row.comment.source
        return 'video:'+source.external_id if source.kind=='youtube' and source.external_id else 'source:'+str(row.source_id_snapshot)
    def root(x):
        parent.setdefault(x, x)
        if parent[x] != x: parent[x] = root(parent[x])
        return parent[x]
    for r in rows:
        a, b = root(source_key(r)), root('text:' + canonical(r.text))
        parent[b] = a
    groups = {}
    for r in rows: groups.setdefault(root(source_key(r)), []).append(r)
    names = sorted(groups); random.Random(seed).shuffle(names)
    if len(names) < 3:
        raise ValueError('Chưa đủ ba nhóm nguồn độc lập để tách train/dev/test.')
    n = len(names); split_names = {'validation': names[:max(1, n // 5)], 'test': names[max(1, n // 5):2 * max(1, n // 5)], 'train': names[2 * max(1, n // 5):]}
    splits = {k: [{'id': r.comment_id, 'approval_id': r.pk, 'text': r.text, 'label': r.label, 'source': r.source_id_snapshot, 'source_group':source_key(r)}
                  for name in values for r in groups[name]] for k, values in split_names.items()}
    keys = {r['key'] for r in schema_labels(schema)}
    if any({r['label'] for r in values} != keys for values in splits.values()):
        raise ValueError('Tách theo nguồn chưa đủ mọi lớp ở train/dev/test. Thu thêm dữ liệu nguồn, không chuyển test để làm đẹp điểm.')
    snapshot = {'schema_sha256': schema.sha256, 'seed': seed, 'splits': splits, 'demo': project.is_demo,
                'protocol': 'source-grouped; canonical duplicate groups; test never selects parameters or activation'}
    from studio.models import PredictionPair
    used_examples={example['approval_id'] for pair in PredictionPair.objects.filter(run__project=project)
                   for example in pair.branches.get('api',{}).get('examples',[])}
    if any(row['approval_id'] in used_examples for row in splits['test']):
        raise ValueError('Test dự kiến chứa phản hồi đã dùng trong prompt. Chốt tập giữ riêng trước retrieval hoặc thu nguồn mới; không coi đây là test độc lập.')
    dataset = FeedbackDataset.objects.create(project=project, schema=schema, seed=seed, sha256=checksum(snapshot), snapshot=snapshot)
    # Reserving test IDs also prevents all future retrieval/training from these rows.
    for row in splits['test']:
        DataPartition.objects.update_or_create(comment_id=row['id'], defaults={'role': 'test'})
    return dataset
