# -*- coding: utf-8 -*-
"""
vECU 适任性评估 Agent（毕业设计）
核心功能：多轮对话需求解析 + 确定性规则拦截
- 使用 st.chat_input / st.chat_message 实现类 ChatGPT 对话界面
- 调用 DeepSeek API（OpenAI SDK）逐轮提取 4 个测试指标
- is_complete 为 true 时进入规则引擎，进行硬门槛拦截评估
"""

import json
import os

import streamlit as st
from openai import OpenAI

# ==================== API 配置 ====================
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))

# 安全检查：如果读不到 Key，直接停止程序并提示
if not DEEPSEEK_API_KEY:
    st.error("❌ 未检测到 DEEPSEEK_API_KEY！请检查本地系统环境变量，或在云端 Secrets 中配置。")
    st.stop()

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"   # DeepSeek 对话模型
TEMPERATURE = 0.1         # 低温度，保证解析结果稳定

# ==================== 系统 Prompt ====================
SYSTEM_PROMPT = """你是一个汽车电子测试需求收集助手，服务于 vECU（虚拟电子控制单元）适任性评估系统。
你的任务：与用户多轮对话，从用户需求中提取 4 个关键指标，并在信息齐全后输出结构化结果。

需要提取的 4 个指标：
1. test_goal：测试类型，取值只能是 "功能"、"通信"、"性能"、"未提及"。
2. bus_type：总线类型，取值只能是 "真实CAN"、"虚拟CAN"、"以太网"、"未提及"。
3. latency：延迟要求，提取为纯数字（单位毫秒 ms），需求中没有提到则填 null。
4. hw_dependency：是否需要物理硬件，布尔值 true/false。未提及硬件时默认填 false。

每轮对话，你必须输出一个纯 JSON 对象，只包含以下两个字段：

"is_complete"：布尔值。
- 4 个指标中只要有一个是 "未提及" 或 null，就填 false。
- 4 个指标全部有确切值时，填 true。
- 特例：若用户明确表示"没有延迟/响应时间要求"，latency 填 null 且 is_complete 填 true（用户已明确确认，视为信息齐全，避免反复追问）。

"reply"：
- 若 is_complete 为 false：这里是反问用户的一句话，用自然的中文指出还缺哪些信息、请用户补充。例如："请问测试的总线类型是什么？是虚拟CAN、真实CAN还是以太网？另外有没有延迟或响应时间要求？"
- 若 is_complete 为 true：这里是一个结构化字典，包含上述 4 个指标，形如：
  {"test_goal":"通信","bus_type":"虚拟CAN","latency":20,"hw_dependency":false}

示例：
用户输入："我想测一下刹车功能的通信"
输出：{"is_complete":false,"reply":"请问测试的总线类型是什么？是虚拟CAN、真实CAN还是以太网？另外有没有延迟或响应时间要求？"}

用户输入："虚拟CAN，要求 20ms 内响应，不需要物理硬件"
输出：{"is_complete":true,"reply":{"test_goal":"通信","bus_type":"虚拟CAN","latency":20,"hw_dependency":false}}

【极度重要】输出格式要求：
- 只输出一个纯 JSON 对象字符串，除此之外绝对不许输出任何其他内容。
- 绝对禁止使用 Markdown 代码块标记（如 ```json 或 ```），禁止任何解释文字、前后缀、客套话。
- 禁止多余的空格和换行，输出必须是紧凑的单行 JSON。
- 必须使用标准双引号，保证输出能被 Python 的 json.loads() 函数直接解析。"""

# ==================== 会话状态初始化 ====================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []      # 对话历史：[{"role": "user"/"assistant", "content": "..."}]
if "is_ready" not in st.session_state:
    st.session_state.is_ready = False       # 需求是否收集完整（is_complete == true）
if "final_metrics" not in st.session_state:
    st.session_state.final_metrics = None   # 最终提取的 4 个指标字典

GREETING = (
    "你好！我是 **vECU 适任性评估 Agent** 🤖\n\n"
    "请描述你的测试需求，我会逐步收集以下 4 项信息：\n"
    "1. 测试类型（功能 / 通信 / 性能）\n"
    "2. 总线类型（真实CAN / 虚拟CAN / 以太网）\n"
    "3. 延迟要求（毫秒）\n"
    "4. 是否需要物理硬件\n\n"
    "例如：*“我想在虚拟总线上测一下刹车功能的通信，要求 20ms 内响应，不需要物理硬件”*"
)

# ==================== 页面 UI ====================
st.set_page_config(page_title="vECU 适任性评估 Agent", page_icon="🚗")
st.title("vECU 适任性评估 Agent")
st.caption("多轮对话收集测试需求 → 大模型提取指标 → 规则引擎硬门槛拦截")

# 首次启动时加入欢迎语
if not st.session_state.chat_history:
    st.session_state.chat_history.append({"role": "assistant", "content": GREETING})

# 渲染历史消息
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==================== 聊天输入与核心逻辑 ====================
if prompt := st.chat_input("请输入测试需求……"):
    # 1) 记录并展示用户消息
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) 调用大模型（带完整多轮上下文）
    with st.chat_message("assistant"):
        with st.spinner("🤖 正在解析……"):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}]
                    + [{"role": m["role"], "content": m["content"]}
                       for m in st.session_state.chat_history],
                    temperature=TEMPERATURE,
                )
            except Exception as e:
                st.error(f"❌ 请求 DeepSeek API 失败，请检查网络或 API Key：{e}")
            else:
                raw_output = response.choices[0].message.content or ""

                # 3) 解析大模型返回的 JSON
                try:
                    data = json.loads(raw_output.strip())
                except (json.JSONDecodeError, TypeError):
                    st.error("大模型输出格式错误")
                    st.code(raw_output, language="text")
                else:
                    # 结构校验：必须包含 is_complete 和 reply 两个字段
                    if not isinstance(data, dict) or "is_complete" not in data or "reply" not in data:
                        st.error("大模型输出格式错误")
                        st.code(raw_output, language="text")
                    elif data["is_complete"] is True and isinstance(data["reply"], dict):
                        # 信息齐全：保存最终指标，进入规则引擎
                        st.session_state.is_ready = True
                        st.session_state.final_metrics = data["reply"]
                        summary = (
                            "✅ 需求信息已收集完整，解析结果如下：\n\n"
                            + "\n".join(f"- **{k}**：`{v}`" for k, v in data["reply"].items())
                        )
                        st.session_state.chat_history.append({"role": "assistant", "content": summary})
                        st.markdown(summary)
                    elif data["is_complete"] is False and isinstance(data["reply"], str):
                        # 信息不完整：反问用户，继续多轮对话
                        st.session_state.chat_history.append({"role": "assistant", "content": data["reply"]})
                        st.markdown(data["reply"])
                    else:
                        st.error("大模型输出格式错误")
                        st.code(raw_output, language="text")

# ==================== 规则引擎：硬门槛拦截 ====================
st.markdown("---")
st.subheader("🎯 平台适任性评估结论")

if st.session_state.is_ready and st.session_state.final_metrics is not None:
    metrics = st.session_state.final_metrics
    st.json(metrics)   # 展示最终提取的 4 个指标

    # 规则判定（硬门槛，顺序执行）：
    if metrics.get("hw_dependency") is True:
        st.error("❌ 不支持：当前平台无真实物理硬件")
    elif metrics.get("bus_type") == "真实CAN":
        st.error("❌ 不支持：当前平台仅支持虚拟 CAN")
    else:
        st.success("✅ 支持：允许进入测试")
else:
    st.info("需求信息尚未收集完整，请继续在下方对话框中回答 Agent 的提问……")
