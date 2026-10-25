import time,httpx
from .base import prompt,result
from integrations.secure_http import public_client
class GeminiAdapter:
    def predict(self,text,labels,connection,key,sentence_only=False):
        started=time.perf_counter()
        with public_client(timeout=90) as client:
            response=client.post(connection.base_url.rstrip('/')+'/models/'+connection.model+':generateContent',headers={'x-goog-api-key':key},json={'contents':[{'parts':[{'text':prompt(text,labels,sentence_only)}]}],'generationConfig':{'temperature':0,'responseMimeType':'application/json'}})
        if response.status_code!=200:raise ValueError(f'Gemini HTTP {response.status_code}; kiểm tra khóa, model và hạn mức.')
        try:
            data=response.json();raw=data['candidates'][0]['content']['parts'][0]['text'];u=data.get('usageMetadata',{})
            return result(raw,text,labels,connection.model,started,(u.get('promptTokenCount',0),u.get('candidatesTokenCount',0)+u.get('thoughtsTokenCount',0)),(connection.input_price,connection.output_price),sentence_only=sentence_only)
        except (KeyError,IndexError,TypeError):raise ValueError('Gemini không trả nội dung có thể chấm nhãn.')
