from collections import Counter,defaultdict
from itertools import combinations
from sklearn.metrics import cohen_kappa_score
from studio.models import Annotation,GoldAnnotation

def quality(project):
    rows=list(Annotation.objects.filter(comment__project=project,status='submitted').select_related('user','label'))
    units=defaultdict(dict);counts=Counter();assisted=0
    for a in rows:units[a.comment_id][a.user_id]=(a.label.key if a.label else 'O');counts[a.user_id]+=1;assisted+=a.assisted
    pairs=[]
    for u,v in combinations(sorted(counts),2):
        shared=[d for d in units.values() if u in d and v in d]
        if not shared:continue
        y=[d[u] for d in shared];p=[d[v] for d in shared];agreement=sum(a==b for a,b in zip(y,p))/len(y)
        kappa=float(cohen_kappa_score(y,p)) if len(set(y+p))>1 else None
        pairs.append({'left':u,'right':v,'n':len(y),'agreement':agreement,'kappa':kappa})
    # Nominal Krippendorff alpha: coincidence weighting handles missing raters.
    observed=0.0;n=0;marginal=Counter();eligible=0;unanimous=0
    for d in units.values():
        values=list(d.values());m=len(values)
        if m<2:continue
        eligible+=1;unanimous+=len(set(values))==1;n+=m;c=Counter(values);marginal.update(c)
        observed+=(m*m-sum(k*k for k in c.values()))/(m-1)
    do=observed/n if n else None
    de=(n*n-sum(k*k for k in marginal.values()))/(n*(n-1)) if n>1 else 0
    alpha=1-do/de if do is not None and de>0 else None
    gold={g.comment_id:(g.label.key if g.label else 'O') for g in GoldAnnotation.objects.filter(comment__project=project).select_related('label')}
    by_user=[]
    for uid,count in counts.items():
        own=[a for a in rows if a.user_id==uid];measured=[a for a in own if a.comment_id in gold]
        by_user.append({'id':uid,'name':own[0].user.first_name or own[0].user.username,'submitted':count,'seconds':sum(a.seconds for a in own),'annotations_per_minute':count/(sum(a.seconds for a in own)/60) if sum(a.seconds for a in own)>0 else None,'against_gold_n':len(measured),'against_gold_accuracy':sum((a.label.key if a.label else 'O')==gold[a.comment_id] for a in measured)/len(measured) if measured else None})
    span_sets=defaultdict(set)
    import json
    for a in rows:span_sets[a.comment_id].add(json.dumps(a.spans,sort_keys=True))
    conflicts=[cid for cid,d in units.items() if len(d)>=2 and (len(set(d.values()))>1 or len(span_sets[cid])>1) and cid not in gold]
    return {'annotations':len(rows),'units':len(units),'overlap_units':eligible,'raw_agreement':unanimous/eligible if eligible else None,'krippendorff_alpha':alpha,'pairs':pairs,'users':by_user,'conflict_ids':conflicts,'gold_count':len(gold),'assisted_annotations':assisted,'limitations':'Độ đồng thuận không đồng nghĩa độ đúng. Thời gian gán tổng quát do client báo, gồm cả thời gian nghỉ. Quản lý có quyền giám sát/xuất dữ liệu nên cần tách vai trò khi đo độc lập. Mẫu có xem AI được ghi assisted; alpha/kappa có thể không xác định khi không có biến thiên.'}
