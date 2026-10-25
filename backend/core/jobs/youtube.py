from core.services.collection import collection_limit
"""Paginated YouTube collection with an exact root/reply cursor at each write."""
import hashlib
import httpx
from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime
from core.models import Source,Comment
from studio.models import UserProfile
from integrations.secrets import decrypt
from studio.services.projects import writable,mutation_guard
from .runner import tick

def run(job,p):
    writable(job.project)
    profile=UserProfile.objects.filter(user=job.actor).first()
    key=decrypt(profile.youtube_key) if profile and profile.youtube_key else settings.YOUTUBE_API_KEY
    if not key:raise ValueError('Chưa cấu hình YouTube API key ở tài khoản hoặc .env.')
    source=Source.objects.get(project=job.project,pk=p['source_id'])
    cp=dict(job.checkpoint or {})
    if cp.get('complete'):return {'imported_total':cp.get('count',0),'complete':True}
    cp={'count':0,'page_token':'','root_index':0,'root_done':False,'reply_token':'','reply_index':0,**cp}
    limit=collection_limit(p.get('limit'))
    source.fetch_state='running';source.save(update_fields=['fetch_state'])
    def checkpoint():
        Source.objects.filter(pk=source.id).update(checkpoint=cp)
        tick(job,cp['count']/limit*100 if limit else 0,f"Đã thu {cp['count']}{'/'+str(limit) if limit else ''} bình luận và phản hồi",dict(cp))
    def save(item,parent=''):
        sn=item['snippet'];text=(sn.get('textOriginal') or sn.get('textDisplay') or '').strip()
        if not text:return
        with transaction.atomic():
            mutation_guard(job.project,job.actor,True)
            context=Comment.objects.filter(project=job.project,external_id=parent).values_list('text',flat=True).first() if parent else ''
            _,created=Comment.objects.get_or_create(project=job.project,digest=hashlib.sha256(text.encode()).hexdigest(),defaults={'source':source,'text':text,'external_id':item['id'],'author':sn.get('authorDisplayName','')[:200],'parent_external_id':parent,'context':context or '', 'published_at':parse_datetime(sn.get('publishedAt',''))})
            cp['count']+=int(created)
    def get(client,endpoint,args):
        checkpoint()
        response=client.get('https://www.googleapis.com/youtube/v3/'+endpoint,params={'key':key,**args})
        if response.status_code!=200:raise ValueError(f'YouTube HTTP {response.status_code}; kiểm tra khóa, quota và video.')
        return response.json()
    with httpx.Client(timeout=45,follow_redirects=False) as client:
        if not source.metadata:
            items=get(client,'videos',{'part':'snippet,statistics','id':p['video_id']}).get('items',[])
            if items:
                source.metadata={'title':items[0]['snippet']['title'],'channel':items[0]['snippet']['channelTitle'],'statistics':items[0].get('statistics',{})};source.name=source.metadata['title'][:200];source.save(update_fields=['name','metadata'])
        while (limit is None or cp['count']<limit) and not cp.get('complete'):
            args={'videoId':p['video_id'],'part':'snippet','maxResults':100,'textFormat':'plainText'}
            if cp['page_token']:args['pageToken']=cp['page_token']
            page=get(client,'commentThreads',args);roots=page.get('items',[])
            while cp['root_index']<len(roots) and (limit is None or cp['count']<limit):
                item=roots[cp['root_index']];root=item['snippet']['topLevelComment']
                if not cp['root_done']:
                    save(root);cp['root_done']=True;checkpoint()
                if p.get('include_replies',True) and item['snippet'].get('totalReplyCount',0):
                    while not cp.get('replies_done') and (limit is None or cp['count']<limit):
                        args={'parentId':root['id'],'part':'snippet','maxResults':100,'textFormat':'plainText'}
                        if cp['reply_token']:args['pageToken']=cp['reply_token']
                        replies=get(client,'comments',args)
                        values=replies.get('items',[])
                        while cp['reply_index']<len(values) and (limit is None or cp['count']<limit):
                            save(values[cp['reply_index']],root['id']);cp['reply_index']+=1;checkpoint()
                        if cp['reply_index']<len(values):break
                        cp['reply_index']=0;cp['reply_token']=replies.get('nextPageToken','')
                        if not cp['reply_token']:cp['replies_done']=True
                        checkpoint()
                    if not cp.get('replies_done'):break
                cp.update(root_index=cp['root_index']+1,root_done=False,reply_index=0,reply_token='',replies_done=False);checkpoint()
            if cp['root_index']>=len(roots):
                cp.update(page_token=page.get('nextPageToken',''),root_index=0,root_done=False,reply_index=0,reply_token='',replies_done=False)
                if not cp['page_token']:cp['complete']=True
                checkpoint()
    source.refresh_from_db();source.fetch_state='complete' if cp.get('complete') else 'paused';source.checkpoint=cp;source.save(update_fields=['fetch_state','checkpoint'])
    return {'imported_total':cp['count'],'complete':bool(cp.get('complete')),'resume':'Cursor gốc và replies được lưu sau từng mẫu. Trang API được tải lại khi tiếp tục; ID và digest loại trùng.'}
