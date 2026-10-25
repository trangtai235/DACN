from .providers.gemini import GeminiAdapter
from .providers.openai_compatible import OpenAICompatibleAdapter
from .providers.ollama import OllamaAdapter
from .providers.base import validate_endpoint
from .secrets import decrypt
REGISTRY={'gemini':GeminiAdapter,'openai_compatible':OpenAICompatibleAdapter,'ollama':OllamaAdapter}
def predict(connection,text,labels):
    if not connection.enabled:raise ValueError('Kết nối đang tắt.')
    validate_endpoint(connection.base_url)
    adapter=REGISTRY.get(connection.kind)
    if not adapter:raise ValueError('Provider chưa được đăng ký.')
    key=decrypt(connection.encrypted_key)
    if connection.kind!='ollama' and not key:raise ValueError('Chưa lưu API key cho kết nối.')
    return adapter().predict(text,labels,connection,key)
def snapshot(c):return {'id':c.id,'name':c.name,'kind':c.kind,'base_url':c.base_url,'model':c.model,'input_price':c.input_price,'output_price':c.output_price,'configured_at':c.updated_at.isoformat()}
