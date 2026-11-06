"""基础需求模型、离线解析、确定性评估。示例能力不代表真实平台。"""
import csv
import io
import json
import re
import math

FIELDS = dict(goal=None, interface=None, hardware=None, timing=None, latency_ms=None,
              memory_gib=None, fault=None)
ENUMS = {'interface': ['虚拟CAN', '真实CAN', '以太网', '无', 'SOME/IP', 'DDS', 'DoIP'],
         'timing': ['无要求', '有要求'], 'fault': ['无', '丢弃', '延迟']}

def validate(data):
    if not isinstance(data, dict):
        raise ValueError('需求必须是 JSON 对象')
    if set(data) - set(FIELDS):
        raise ValueError('未知字段：' + ', '.join(set(data) - set(FIELDS)))
    out = FIELDS | data
    for k, allowed in ENUMS.items():
        if out[k] is not None and out[k] not in allowed:
            raise ValueError(f'{k} 必须取值于 {allowed}')
    if out['hardware'] is not None and type(out['hardware']) is not bool:
        raise ValueError('hardware 必须为 true/false/null')
    if out['goal'] is not None and (not isinstance(out['goal'], str) or not out['goal'].strip()):
        raise ValueError('goal 必须为非空文本')
    for k in ('latency_ms', 'memory_gib'):
        if out[k] is not None and (type(out[k]) not in (int, float) or not math.isfinite(out[k]) or out[k] <= 0):
            raise ValueError(f'{k} 必须为正数')
    if out['timing'] == '无要求' and out['latency_ms'] is not None:
        raise ValueError('无时序要求与延迟数值冲突')
    if out['latency_ms'] is not None:
        out['timing'] = '有要求'
    return out

def parse_local(text):
    """有限关键词演示解析；不声称通用自然语言理解。未知值保留 null。"""
    d = FIELDS.copy()
    if any(x in text for x in ('验证', '测试', '检查')):
        d['goal'] = text
    for token in ENUMS['interface']:
        if token != '无' and token.lower() in text.lower():
            d['interface'] = token
    if any(x in text for x in ('无通信', '不需要通信')):
        d['interface'] = '无'
    if any(x in text for x in ('不需要物理硬件', '无硬件依赖', '不依赖硬件')):
        d['hardware'] = False
    elif any(x in text for x in ('需要物理硬件', '真实传感器', '真实电机', '电压', '电气', '波形')):
        d['hardware'] = True
    if any(x in text for x in ('无时序要求', '无延迟要求', '没有延迟要求')):
        d['timing'] = '无要求'
    m = re.search(r'(\d+(?:\.\d+)?)\s*(ms|毫秒|微秒|μs|us|秒)', text, re.I)
    if m:
        d['latency_ms'] = float(m[1]) * ({'秒': 1000, '微秒': .001, 'μs': .001, 'us': .001}.get(m[2].lower(), 1))
        d['timing'] = '有要求'
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:GiB|GB)', text, re.I)
    if m:
        d['memory_gib'] = float(m[1]) * (1 if 'gib' in m[0].lower() else 10**9 / 2**30)
    if '无故障注入' in text:
        d['fault'] = '无'
    elif '丢弃' in text or '丢包' in text:
        d['fault'] = '丢弃'
    elif '延迟注入' in text:
        d['fault'] = '延迟'
    return validate(d)

def evaluate(data, env):
    d = validate(data)
    checks, missing, failures, conditions = [], [], [], []
    def add(rule, result, reason, evidence):
        checks.append(dict(规则=rule, 状态=result, 说明=reason, 依据=evidence))
    for key, question in [('goal','请说明具体测试目标'), ('interface','请说明接口，或确认无通信'),
                          ('hardware','是否需要物理硬件？'), ('timing','是否有时序要求？'),
                          ('fault','是否需要故障注入？')]:
        if d[key] is None:
            missing.append(question)
    if d['hardware'] is True:
        failures.append('该演示平台不支持真实硬件验证')
        add('H01', '不满足', failures[-1], env['evidence'])
    elif d['hardware'] is False:
        add('H01', '满足', '用户确认无物理硬件依赖', '需求.hardware')
    if d['interface'] is not None:
        state = env['interfaces'].get(d['interface'], 'unknown')
        if state == 'unsupported':
            failures.append('接口不支持：' + d['interface'])
        elif state == 'unknown':
            missing.append('需核实平台接口能力：' + d['interface'])
        add('I01', state, d['interface'], env['evidence'])
    if d['timing'] == '有要求':
        missing.append('需补充相同负载、测量范围和统计口径下的时序验证证据')
        add('T01', '未知', '平台没有可用于保证响应时间的实测证据', env['evidence'])
    elif d['timing'] == '无要求':
        add('T01', '不适用', '用户不考核时序', '需求.timing')
    if d['memory_gib'] is not None:
        ok = d['memory_gib'] <= env['memory_gib']
        if not ok:
            failures.append('内存需求超过单实例容量')
        add('R01', '满足' if ok else '不满足', f"需求 {d['memory_gib']} / 容量 {env['memory_gib']} GiB", env['evidence'])
    if d['fault'] in ('丢弃', '延迟'):
        if d['interface'] == '虚拟CAN':
            conditions.append('需配置虚拟 CAN 应用层故障注入，仅验证功能逻辑')
            add('F01', '需配置', conditions[-1], env['evidence'])
        else:
            missing.append('需核实该接口的故障注入能力')
    status = '不支持' if failures else '信息不足' if missing else '有条件支持' if conditions else '支持'
    # 示例匹配指数：只在需求完整且无硬失败时提供，不用于替代硬约束。
    score = None if failures or missing else round(100 * (1 - .2 * bool(conditions)))
    return dict(status=status, score=score, failures=failures, missing=missing,
                conditions=conditions, checks=checks, environment=env['id'],
                environment_version=env['version'], rule_version='demo-1.0',
                scope='仅覆盖接口、硬件、时序、内存及注入的基础筛选；未校验软件兼容性和全部资源。')

def read_upload(name, content):
    """返回 (位置, 结构化对象或文本)，禁止静默截断。"""
    if len(content) > 2 * 1024 * 1024:
        raise ValueError('演示版文件上限 2 MiB')
    ext = name.rsplit('.', 1)[-1].lower()
    if ext == 'json':
        obj = json.loads(content.decode('utf-8-sig'))
        rows = obj if isinstance(obj, list) else [obj]
        return [(f'{name} / 条目 {i+1}', validate(row)) for i, row in enumerate(rows)]
    if ext == 'csv':
        rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
        if not rows:
            raise ValueError('CSV 没有数据行')
        result = []
        for i, row in enumerate(rows):
            if set(row) != {'text'}:
                raise ValueError('CSV 模板只接受 text 列，每行一条自然语言需求')
            result.append((f'{name} / 第 {i+2} 行', row['text']))
        return result
    if ext in ('txt', 'md'):
        text = content.decode('utf-8-sig').strip()
        if not text:
            raise ValueError('文件为空')
        return [(name, text)]
    raise ValueError('目前支持 JSON、CSV、TXT、Markdown')
