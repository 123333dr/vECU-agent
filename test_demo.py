import json
from pathlib import Path
from streamlit.testing.v1 import AppTest
from core import parse_local, evaluate, read_upload, validate
root = Path(__file__).parent
env = json.loads((root/'capabilities.json').read_text(encoding='utf-8'))
scenarios = [
 ('支持','测试虚拟CAN解码，不需要物理硬件，无时序要求，无故障注入，内存2GiB。'),
 ('不支持','测试真实CAN电压，需要物理硬件，无时序要求，无故障注入。'),
 ('信息不足','测试刹车功能。'),
 ('有条件支持','测试虚拟CAN丢弃报文，不需要物理硬件，无时序要求。'),
 ('信息不足','测试以太网通信，不需要物理硬件，要求500微秒，无故障注入。'),
 ('不支持','测试虚拟CAN解码，不需要物理硬件，无时序要求，无故障注入，内存8GiB。')]
output = []
for expected,text in scenarios:
    req = parse_local(text)
    result = evaluate(req,env)
    assert result['status'] == expected, result
    output.append({'input':text,'requirement':req,'result':result})
assert parse_local('要求500微秒')['latency_ms'] == .5
assert parse_local('测试功能')['hardware'] is None
try:
    validate({'latency_ms':-1})
    raise AssertionError('negative accepted')
except ValueError: pass
assert len(read_upload('demo.json',json.dumps([parse_local(scenarios[0][1])]).encode())) == 1
assert len(read_upload('demo.csv','text\n测试刹车功能\n'.encode())) == 1
app = AppTest.from_file(str(root/'app.py'), default_timeout=30).run()
assert not app.exception, app.exception
for index, (expected, _) in enumerate(scenarios[:5]):
    app.button[index].click().run()
    assert not app.exception, app.exception
    next(b for b in app.button if b.label == '确认并评估').click().run()
    assert app.session_state['result']['status'] == expected
    assert not app.exception, app.exception
(root/'demo_results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
samples = root/'samples'
samples.mkdir(exist_ok=True)
(samples/'requirements.json').write_text(json.dumps([parse_local(t) for _,t in scenarios],ensure_ascii=False,indent=2),encoding='utf-8')
(samples/'requirements.csv').write_text('text\n'+'\n'.join(t for _,t in scenarios),encoding='utf-8-sig')
print('PASS: 6 assessment scenarios, validation/upload checks, 5 Streamlit UI flows')


