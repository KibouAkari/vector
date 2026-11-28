"""Small nginx lexer used for additive metadata logging. No regex rewriting of quoted text."""
import re

FORMAT = '''log_format vector_metadata escape=json '{"time_iso8601":"$time_iso8601","remote_addr":"$remote_addr","server_name":"$server_name","request_method":"$request_method","status":"$status","bytes_sent":"$bytes_sent","request_time":"$request_time"}';'''


def directives(source):
    tokens = list(re.finditer(r'''\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};\#"']+''', source))
    stack, words = [], []
    for token in tokens:
        text = token.group()
        if text.isspace() or text.startswith('#'):
            continue
        if text == '{':
            name = words[0][0] if words else ''
            stack.append((name, token.end()))
            yield ('block', name, token.end(), tuple(stack))
            words = []
        elif text == '}':
            if stack:
                stack.pop()
            words = []
        elif text == ';':
            if words:
                yield ('directive', [word[0].strip('\'"') for word in words], token.end(), tuple(stack))
            words = []
        else:
            words.append((text, token.start()))


def instrument(source, log_path, main=False):
    """Keep access_log off; retain existing logs. Only modify known HTTP scopes."""
    if 'vector_metadata' in source:
        return source, False
    items = list(directives(source))
    scopes, http = {}, next((item for item in items if item[0]=='block' and item[1]=='http'), None)
    for kind, args, end, scope in items:
        if kind=='directive' and args[0]=='access_log':
            scopes.setdefault(scope, []).append((args, end))
    insertions = []
    directive = f'access_log {log_path} vector_metadata buffer=16k flush=1s;'
    if main:
        if not http:
            return source, False
        insertions.append((http[2], '\n    '+FORMAT+'\n'))
        if not any(args[1:2]==['off'] for args,_ in scopes.get(http[3], [])):
            insertions[-1] = (http[2], '\n    '+FORMAT+'\n    '+directive+'\n')
    for scope, logs in scopes.items():
        if not scope or any(name=='stream' for name,_ in scope) or main and scope==http[3]:
            continue
        if scope[-1][0] not in ('http','server','location','if','limit_except') or any(args[1:2]==['off'] for args,_ in logs):
            continue
        insertions.append((logs[0][1], '\n    '+directive))
    for at, value in sorted(insertions, reverse=True):
        source=source[:at]+value+source[at:]
    return source, bool(insertions)


def listed_files(dump):
    return list(dict.fromkeys(re.findall(r'^# configuration file (/[^\n]+):$',dump,re.M)))
