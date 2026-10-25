import base64,hashlib
from cryptography.fernet import Fernet,InvalidToken
from django.conf import settings

def cipher():
    key=hashlib.sha256(('annotaflow-secrets-v1:'+settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))
def encrypt(value):return cipher().encrypt(value.encode()).decode() if value else ''
def decrypt(value):
    if not value:return ''
    try:return cipher().decrypt(value.encode()).decode()
    except InvalidToken:raise ValueError('Không giải mã được khóa. Cần lưu lại khóa sau khi thay SECRET_KEY.')
