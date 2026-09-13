"""Self-contained HTTP deadline and evidence redaction helpers."""
import base64
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

SECRET_NAME = re.compile(r"(?i)(authorization|cookie|password|passwd|token|api.?key|secret|access.?key|private.?key|signature)")

def redact_json(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SECRET_NAME.search(str(k)) else redact_json(v) for k,v in value.items()}
    if isinstance(value, list): return [redact_json(v) for v in value]
    return redact(value) if isinstance(value, str) else value

def redact(value):
    value = str(value)
    value = re.sub(r"(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"([?&][^=&\s]+)=([^&#\s]*)", r"\1=[REDACTED]", value)
    value = re.sub(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=._~-]+", "[REDACTED]", value)
    key = r"(?:authorization|proxy-authorization|cookie|set-cookie|password|passwd|[\w-]*token|api[_-]?key|[\w-]*secret|access[_-]?key|private[_-]?key|signature)"
    value = re.sub(r'(?i)(["\']?' + key + r'["\']?\s*[=:]\s*)(?:"(?:\\.|[^"\\])*"|\'[^\']*\'|[^\s,;]+)', r'\1[REDACTED]', value)
    value = re.sub(r"(?im)^\s*((?:authorization|proxy-authorization|cookie|set-cookie):).*$", r"\1 [REDACTED]", value)
    return value

def redact_text(value):
    try: return json.dumps(redact_json(json.loads(value)), ensure_ascii=False)
    except (ValueError, TypeError):
        plain_log = re.match(r"^\s*\[(?:[A-Za-z][A-Za-z ]*|\d{4}-\d\d-\d\d[^\]]*)\](?:\s|$)", str(value))
        if str(value).lstrip().startswith(("{", "[")) and not plain_log: return "[unparsed structured content omitted]"
        return redact(value)

def safe_url(url):
    p = urlsplit(url)
    host = p.hostname or ""
    if ":" in host: host = "[" + host + "]"
    if p.port: host += ":" + str(p.port)
    query = urlencode([(k,"[REDACTED]") for k,v in parse_qsl(p.query,keep_blank_values=True)])
    return urlunsplit((p.scheme,host,p.path,query,""))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

def network_worker(payload):
    try:
        request = Request(payload['url'], method=payload['method'],
                          headers=payload['headers'], data=base64.b64decode(payload['body']) if payload['body'] is not None else None)
        try: response = build_opener(NoRedirect()).open(request, timeout=payload['timeout'])
        except HTTPError as exc: response = exc
        with response:
            raw = response.read(payload['limit'] + 1)
            return {'status_code': response.code, 'headers':dict(response.headers.items()),
                    'body':base64.b64encode(raw[:payload['limit']]).decode(), 'truncated':len(raw)>payload['limit']}
    except Exception as exc:
        return {'error':type(exc).__name__}

def bounded_request(url, method, headers, body, timeout, limit):
    if not math.isfinite(timeout) or timeout <= 0: return {'error':'total_timeout'}
    payload = {'url':url,'method':method,'headers':headers,'body':base64.b64encode(body).decode() if body is not None else None,
               'timeout':timeout,'limit':limit}
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve())], input=json.dumps(payload).encode(),
                                 capture_output=True, timeout=timeout, check=False)
        if process.returncode: return {'error':'network_worker_failed'}
        result = json.loads(process.stdout)
        if 'body' in result: result['body'] = base64.b64decode(result['body'],validate=True)
        return result
    except subprocess.TimeoutExpired: return {'error':'total_timeout'}
    except (OSError,ValueError): return {'error':'network_worker_failed'}

if __name__ == '__main__':
    try:
        payload=json.loads(sys.stdin.buffer.read(2*1024*1024))
        print(json.dumps(network_worker(payload)))
    except Exception:
        print(json.dumps({'error':'invalid_network_request'}))
