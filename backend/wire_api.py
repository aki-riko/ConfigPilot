# coding: utf-8
"""Codex ``wire_api`` 协议表：界面只显示协议名，落盘标识由这里映射。

OpenAI 对外有两套线协议：

* Responses API —— ``/v1/responses``，Codex 写 ``wire_api = "responses"``；
* Chat Completions API —— ``/v1/chat/completions``，Codex 写 ``wire_api = "chat"``。

Codex 的 ``wire_api`` 只接受 ``responses`` / ``chat`` 两个字面量（见上游
``codex-rs/model-provider-info`` 的 ``enum WireApi``），且新版 Codex 已经拒绝
``chat`` 并直接报错（openai/codex#7782）。因此这里把 Chat Completions 标成
已废弃但保留可选：旧版 Codex 和只暴露 chat 端点的中转站仍然要填它。
"""

DEPRECATION_SUFFIX = "（已废弃）"

WIRE_API_PROTOCOLS = (
    {
        "value": "responses",
        "label": "Responses API",
        "endpoint": "/v1/responses",
        "deprecated": False,
    },
    {
        "value": "chat",
        "label": "Chat Completions API",
        "endpoint": "/v1/chat/completions",
        "deprecated": True,
    },
)


def option_list():
    """下拉框候选：``value`` 是写入 config.toml 的标识，``text`` 是界面显示名。"""
    return [
        {
            "value": protocol["value"],
            "text": display_label(protocol["value"]),
            "endpoint": protocol["endpoint"],
            "deprecated": protocol["deprecated"],
        }
        for protocol in WIRE_API_PROTOCOLS
    ]


def display_label(value):
    """把配置里的 ``wire_api`` 标识换成显示名；未知值原样返回，不伪装成协议名。"""
    text = str(value or "").strip()
    for protocol in WIRE_API_PROTOCOLS:
        if text.lower() == protocol["value"].lower():
            return (protocol["label"] + DEPRECATION_SUFFIX
                    if protocol["deprecated"] else protocol["label"])
    return text


def canonical_value(name):
    """显示名/端点/标识 → 写入用的 ``wire_api`` 标识；认不出的值原样透传。

    透传是刻意的：历史 config.toml 里可能留着第三方值，静默改写成
    ``responses`` 会让用户看到和落盘不一致的结果。
    """
    text = str(name or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    for protocol in WIRE_API_PROTOCOLS:
        accepted = {
            protocol["value"].lower(),
            protocol["label"].lower(),
            protocol["endpoint"].lower(),
            (protocol["label"] + DEPRECATION_SUFFIX).lower(),
        }
        if lowered in accepted:
            return protocol["value"]
    return text
