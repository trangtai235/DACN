import time,httpx
from .base import prompt,result
class OpenAICompatibleAdapter:
    def predict(self,text,labels,connection,key):
        started=time.perf_counter()
        with httpx.Client(timeout=90,follow_redirects=False) as client:
            response=client.post(connection.base_url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+key},json={'model':connection.model,'messages':[{'role':'user','content':prompt(text,labels)}],'temperature':0,'response_format':{'type':'json_object'}})
        if response.status_code!=200:raise ValueError(f'API chat/completions HTTP {response.status_code}; kiểm tra endpoint, model và quyền.')
        try:
            data=response.json();raw=data['choices'][0]['message']['content'];u=data.get('usage',{})
            return result(raw,text,labels,connection.model,started,(u.get('prompt_tokens',0),u.get('completion_tokens',0)),(connection.input_price,connection.output_price))
        except (KeyError,IndexError,TypeError):raise ValueError('API không trả nội dung chat hợp lệ.')
