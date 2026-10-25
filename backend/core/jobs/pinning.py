import hashlib,json
from pathlib import Path
from .runner import tick

def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def connection_identity(c):
    if not c:return None
    return {'id':c.id,'kind':c.kind,'base_url':c.base_url,'model':c.model,'input_price':c.input_price,'output_price':c.output_price}
def pin(job,identity):
    prior=job.checkpoint.get('identity')
    if prior and prior!=identity:raise ValueError('Model/API, bộ nhãn hoặc tập test đã đổi sau checkpoint. Tạo lượt mới để không trộn kết quả.')
    tick(job,job.progress,'Đã khóa cấu hình thực nghiệm',{'identity':identity})
