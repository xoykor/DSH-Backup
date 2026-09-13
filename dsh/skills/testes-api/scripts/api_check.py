#!/usr/bin/env python3
"""Run explicit HTTP assertions with per-request and total wall-clock deadlines."""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from net_common import bounded_request, redact, redact_text, safe_url, SECRET_NAME

class SpecError(ValueError): pass

def scalar_match(actual, expected):
    if not isinstance(expected, dict): return type(actual) is type(expected) and actual == expected
    if not expected or set(expected) - {'equals','contains'}: return False
    if 'equals' in expected and not scalar_match(actual, expected['equals']): return False
    if 'contains' in expected:
        needle = expected['contains']
        if isinstance(actual,str) and isinstance(needle,str): return needle in actual
        if isinstance(actual,list): return any(scalar_match(v,needle) for v in actual)
        if isinstance(actual,dict) and isinstance(needle,str): return needle in actual
        return False
    return True

def json_path(value,path):
    for part in path.split('.'):
        if isinstance(value,dict) and part in value: value=value[part]
        elif isinstance(value,list) and part.isdigit() and int(part)<len(value): value=value[int(part)]
        else: return False,None
    return True,value

def matcher_valid(value):
    return not isinstance(value,dict) or bool(value) and not (set(value)-{'equals','contains'})

def validate_spec(spec):
    if not isinstance(spec,dict) or set(spec)-{'requests','allow_mutations'}: raise SpecError('invalid spec fields')
    if not isinstance(spec.get('requests'),list) or not 1<=len(spec['requests'])<=32: raise SpecError('requests must contain 1..32 cases')
    if not isinstance(spec.get('allow_mutations',False),bool): raise SpecError('allow_mutations must be boolean')
    result=[]
    for i,item in enumerate(spec['requests'],1):
        if not isinstance(item,dict) or set(item)-{'name','url','method','headers','body','timeout','expect'}: raise SpecError('invalid request fields')
        url=item.get('url')
        if not isinstance(url,str): raise SpecError('URL is required')
        p=urlsplit(url)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password: raise SpecError('URL must be HTTP(S) without embedded credentials')
        try: p.port
        except ValueError: raise SpecError('invalid port') from None
        method=item.get('method','GET')
        if not isinstance(method,str) or method.upper() not in {'GET','HEAD','POST','PUT','PATCH','DELETE'}: raise SpecError('unsupported method')
        timeout=item.get('timeout',10)
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .05<=timeout<=600: raise SpecError('timeout must be .05..600 seconds')
        headers=item.get('headers',{})
        if not isinstance(headers,dict) or any(not isinstance(k,str) or not isinstance(v,str) or '\n' in k+v or '\r' in k+v for k,v in headers.items()): raise SpecError('headers must be strings without newlines')
        expect=item.get('expect',{'status':200})
        if not isinstance(expect,dict) or not expect or set(expect)-{'status','headers','body'}: raise SpecError('expect needs supported assertions')
        if 'status' in expect and (not matcher_valid(expect['status']) or isinstance(expect['status'],dict) and 'contains' in expect['status']): raise SpecError('status supports a number or equals:number')
        if 'headers' in expect and (not isinstance(expect['headers'],dict) or not expect['headers'] or any(not matcher_valid(v) for v in expect['headers'].values())): raise SpecError('invalid header matchers')
        body=expect.get('body',{})
        if not isinstance(body,dict) or set(body)-{'equals','contains','fields'}: raise SpecError('invalid body matcher')
        if 'body' in expect and not body: raise SpecError('body must contain assertions')
        if 'equals' in body and not isinstance(body['equals'],str): raise SpecError('body equals must be a string')
        if 'contains' in body and not (isinstance(body['contains'],str) or isinstance(body['contains'],list) and body['contains'] and all(isinstance(x,str) for x in body['contains'])): raise SpecError('body contains must be string or nonempty string list')
        if 'fields' in body and (not isinstance(body['fields'],dict) or not body['fields'] or any(not isinstance(k,str) or not k or not matcher_valid(v) for k,v in body['fields'].items())): raise SpecError('invalid JSON fields')
        name=item.get('name',f'request-{i}')
        if not isinstance(name,str) or len(name)>100: raise SpecError('name must be a string up to 100 characters')
        result.append({**item,'method':method.upper(),'timeout':float(timeout),'name':redact(name),'expect':expect})
    return result

def run_request(item,deadline,body_limit):
    start=time.monotonic()
    result={'name':item['name'],'method':item['method'],'url':safe_url(item['url'])}
    data=item.get('body')
    headers=dict(item.get('headers',{}))
    encoded=None if data is None else data.encode() if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode()
    if encoded is not None:
        headers.setdefault('Content-Type','text/plain; charset=utf-8' if isinstance(data,str) else 'application/json')
    response=bounded_request(item['url'],item['method'],headers,encoded,min(item['timeout'],deadline-start),body_limit)
    result['duration_ms']=round((time.monotonic()-start)*1000)
    if 'error' in response:
        result.update(status='failed_transport',transport='failed',error=response['error'])
        return result
    raw=response['body']; code=response['status_code']; truncated=response['truncated']
    actual_headers={k.lower():v for k,v in response['headers'].items()}
    result.update(transport='http_error_response' if code>=300 else 'response',status_code=code,
                  body_bytes=len(raw),body_sha256=hashlib.sha256(raw).hexdigest(),body_hash_scope='captured_prefix' if truncated else 'full_body',
                  body_truncated=truncated,headers={k:'[present]' for k in actual_headers if not SECRET_NAME.search(k)})
    try: text=raw.decode('utf-8'); valid_text=True
    except UnicodeDecodeError: text=''; valid_text=False
    expect=item['expect']; body=expect.get('body',{})
    parsed=None; valid_json=False
    json_expected='json' in actual_headers.get('content-type','').lower() and item['method'] != 'HEAD' and code not in (204,304) or bool(body.get('fields'))
    if json_expected:
        try:
            if truncated: raise ValueError('truncated')
            parsed=json.loads(text); valid_json=True
        except ValueError: result['json_error']='invalid_json_or_truncated_body'
    result['body_preview']=redact_text(text)[:2000] if valid_text and not truncated else '[binary or truncated body omitted]'
    assertions=[]
    if 'status' in expect: assertions.append({'target':'status','ok':scalar_match(code,expect['status'])})
    for key,value in expect.get('headers',{}).items():
        actual=actual_headers.get(key.lower())
        assertions.append({'target':'headers.'+key,'ok':actual is not None and scalar_match(actual,value)})
    if json_expected: assertions.append({'target':'body.valid_json','ok':valid_json})
    if 'equals' in body: assertions.append({'target':'body.equals','ok':valid_text and not truncated and text==body['equals']})
    contains=body.get('contains',[])
    for needle in [contains] if isinstance(contains,str) else contains:
        assertions.append({'target':'body.contains','ok':valid_text and not truncated and needle in text})
    for path,value in body.get('fields',{}).items():
        exists,actual=json_path(parsed,path)
        assertions.append({'target':'body.fields.'+path,'ok':valid_json and exists and scalar_match(actual,value)})
    result['assertions']=assertions
    result['status']='passed' if assertions and all(a['ok'] for a in assertions) else 'failed_assertion'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',required=True,type=Path); p.add_argument('--output',type=Path)
    p.add_argument('--total-timeout',type=float,default=60); p.add_argument('--body-max-bytes',type=int,default=12000)
    p.add_argument('--allow-mutations',action='store_true'); args=p.parse_args()
    try:
        if not math.isfinite(args.total_timeout) or not .05<=args.total_timeout<=600 or not 1<=args.body_max_bytes<=262144: raise SpecError('timeout .05..600; body limit 1..262144')
        if args.output and (args.output.exists() or args.output.is_symlink()): raise SpecError('output exists; choose a new report')
        if args.spec.stat().st_size>1024*1024: raise SpecError('spec exceeds 1 MiB')
        spec=json.loads(args.spec.read_text()); requests=validate_spec(spec)
        if any(i['method'] not in {'GET','HEAD'} for i in requests) and not (args.allow_mutations and spec.get('allow_mutations')):
            report={'status':'blocked_mutation','error':'requires allow_mutations:true and --allow-mutations'}; code=2
        else:
            start=time.monotonic(); deadline=start+args.total_timeout
            results=[run_request(item,deadline,args.body_max_bytes) for item in requests]
            report={'status':'passed' if all(r['status']=='passed' for r in results) else 'failed',
                    'requests':results,'duration_ms':round((time.monotonic()-start)*1000),'truncated':any(r.get('body_truncated') for r in results)}
            code=0 if report['status']=='passed' else 1
    except (OSError,ValueError) as exc:
        report={'status':'invalid_spec','error':str(exc) if type(exc) is SpecError else type(exc).__name__}; code=2
    rendered=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        try:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            with args.output.open('x',encoding='utf-8') as f: f.write(rendered)
        except OSError:
            print(json.dumps({'status':'report_not_written','report':report})); return 2
    sys.stdout.write(rendered); return code

if __name__=='__main__': raise SystemExit(main())
