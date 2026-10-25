import time,httpx
from .base import prompt,result
class OllamaAdapter:
    def predict(self,text,labels,connection,key):
        started=time.perf_counter();headers={'Authorization':'Bearer '+key} if key else {}
        with httpx.Client(timeout=180,follow_redirects=False) as client:
            response=client.post(connection.base_url.rstrip('/')+'/api/chat',headers=headers,json={'model':connection.model,'messages':[{'role':'user','content':prompt(text,labels)}],'stream':False,'format':'json','options':{'temperature':0}})
        if response.status_code!=200:raise ValueError(f'Ollama HTTP {response.status_code}; kiểm tra server và model đã tải.')
        try:
            data=response.json();raw=data['message']['content']
            return result(raw,text,labels,connection.model,started,(data.get('prompt_eval_count',0),data.get('eval_count',0)),(connection.input_price,connection.output_price))
        except (KeyError,IndexError,TypeError):raise ValueError('Ollama không trả nội dung chat hợp lệ.')
