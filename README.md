# vECU 适任性评估基础原型

原始页面备份：app_original.py。

## 启动

```powershell
cd D:\Project\vECU-Agent
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

浏览器打开 http://localhost:8501 。默认离线模式不需要 API Key。

## 演示

1. 查看“① 平台能力”：P0-DEMO 是人工构造的假设环境。
2. 在“② 需求与文件”依次点击五个快速体验按钮，检查结构化字段。
3. 点击“确认并评估”，打开“③ 评估结果”查看结论、规则、证据和建议。
4. 上传 samples/requirements.json 或 requirements.csv，点击批量评估并下载结果。
5. 新任务先点击侧栏“新建评估”；补充当前需求直接提交文字。

## 模块

- core.py：校验、有限关键词抽取、确定性评估、文件读取。
- capabilities.json：版本化演示能力档案。
- app.py：平台、需求、结果三个页面入口。
- test_demo.py：基础判定、文件读取、字段验证及 Streamlit 交互验证。
- demo_results.json：六个离线实验的完整输入输出。

API 模式可在侧栏填 DeepSeek Key；或使用 DEEPSEEK_API_KEY 环境变量 / Streamlit secrets。模型名可配置。API 调用失败会提示错误，不会自动伪造结论。

## 当前边界

支持 JSON、CSV（text 单列）、TXT、MD；尚未支持 Excel、Word、PDF。TXT/MD 整份只作为一个任务。离线关键词解析不具备通用自然语言理解能力，否定、矛盾及复杂改写需人工修正。单位推荐明确写 GiB。

评估覆盖接口、物理硬件、时序证据、内存和应用层故障注入。尚未实现软件栈兼容性、CPU/并发容量、仿真精度等完整指标。页面匹配指数是演示规则，未经专家标定。上传文件仅保留在当前会话中，不主动落盘。字段来源和版本随报告导出，尚未建设数据库审计。

真实部署前需补齐实际平台能力和验证证据，并调整评估引擎。不要仅将演示档案中的 demo 改为 false。
