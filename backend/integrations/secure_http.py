"""Public HTTPS API connections: validate DNS and pin TLS to the validated IP."""
import ipaddress
import socket
from urllib.parse import urlsplit
import httpx


def public_endpoint(value):
    if not isinstance(value,str) or len(value)>500 or any(ord(c)<33 for c in value) or '\\' in value:
        raise ValueError('Base URL không hợp lệ.')
    try:
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.port not in (None,443):
            raise ValueError('Base URL phải dùng HTTPS cổng 443, không chứa tài khoản, query hoặc fragment.')
        host=url.hostname.lower().rstrip('.')
        if host in ('localhost','metadata.google.internal','host.docker.internal') or host.endswith(('.local','.localhost','.internal','.test')):
            raise ValueError('Không cho phép API truy cập địa chỉ nội bộ hoặc metadata server.')
        try:
            address=ipaddress.ip_address(host)
        except ValueError:
            if '.' not in host or any(not part or not all(c.isalnum() or c=='-' for c in part) for part in host.split('.')):
                raise ValueError('Hostname API không hợp lệ.')
        else:
            if not address.is_global or address.is_multicast:
                raise ValueError('Không cho phép API truy cập địa chỉ nội bộ hoặc metadata server.')
        if any(segment in ('.','..') for segment in url.path.split('/')) or '%' in url.path:
            raise ValueError('Đường dẫn Base URL không hợp lệ.')
        return value.rstrip('/')
    except (ValueError,UnicodeError) as exc:
        if isinstance(exc,ValueError) and str(exc).startswith(('Base URL','Không cho phép','Hostname','Đường dẫn')):raise
        raise ValueError('Base URL không hợp lệ.') from None


def public_addresses(host):
    try:
        records=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError('Không phân giải được hostname API; kiểm tra Base URL.') from None
    addresses=list(dict.fromkeys(row[4][0] for row in records))
    if not addresses or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast for ip in addresses):
        raise ValueError('DNS của API trỏ tới địa chỉ nội bộ hoặc bị cấm.')
    return addresses


class PublicTransport(httpx.HTTPTransport):
    def handle_request(self,request):
        public_endpoint(str(request.url))
        host=request.url.host
        addresses=public_addresses(host)
        # The original hostname remains Host and TLS SNI; the socket uses an IP,
        # so a second DNS resolution cannot redirect the request to an internal IP.
        headers=request.headers.copy()
        headers['Host']=host
        pinned=httpx.Request(request.method,request.url.copy_with(host=addresses[0]),headers=headers,
                             stream=request.stream,extensions={**request.extensions,'sni_hostname':host})
        return super().handle_request(pinned)


def public_client(timeout=20):
    return httpx.Client(transport=PublicTransport(),timeout=timeout,follow_redirects=False,trust_env=False)
