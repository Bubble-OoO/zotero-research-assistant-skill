# -*- coding: utf-8 -*-
"""
deepseek_agent.py
一个最小可用的本地命令行 Agent：用 DeepSeek 官方 API（OpenAI 兼容接口）驱动，
把 SKILL.md 作为 system prompt，把 zotero_tools.py 里的函数注册为 tools，
实现「用自然语言操作 Zotero」。

运行前准备：
    pip install -r requirements.txt
    cp config.example.env .env   # 然后编辑 .env 填好你的 key

运行：
    python scripts/deepseek_agent.py
"""

import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from zotero_tools import TOOL_SCHEMAS, TOOL_DISPATCH  # noqa: E402

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

MAX_TOOL_ROUNDS = 8  # 防止死循环的保险丝


def load_system_prompt():
    skill_md = ROOT_DIR / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    return (
        "你是一个可以直接操作用户 Zotero 文献库的研究助理。"
        "以下是你必须遵守的工作规范（来自 SKILL.md），请严格执行，"
        "尤其是「先检索再回答」和「写操作前必须确认」这两条：\n\n"
        + text
    )


def call_tool(name, arguments_json):
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return {"error": f"未知工具: {name}"}
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"工具参数 JSON 解析失败: {e}"}
    return fn(**args)


def run():
    if not DEEPSEEK_API_KEY:
        print("请先在 .env 中设置 DEEPSEEK_API_KEY（参考 config.example.env）")
        sys.exit(1)

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    messages = [{"role": "system", "content": load_system_prompt()}]

    print("Zotero 研究助理已就绪（输入 exit / quit 退出）")
    print(f"模型: {DEEPSEEK_MODEL}  |  Zotero 模式: {'本地' if os.environ.get('ZOTERO_LOCAL','').lower()=='true' else '云端'}")

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() in ("exit", "quit", "退出"):
            print("再见！")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        for _ in range(MAX_TOOL_ROUNDS):
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                # 把模型的这次回复（含 tool_calls）加入历史
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )
                for tc in msg.tool_calls:
                    print(f"  [调用工具] {tc.function.name}({tc.function.arguments})")
                    result = call_tool(tc.function.name, tc.function.arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                # 继续下一轮，让模型根据工具结果生成最终回答或再调用别的工具
                continue
            else:
                print(f"\n助理: {msg.content}")
                messages.append({"role": "assistant", "content": msg.content})
                break
        else:
            print("\n[提示] 工具调用轮次过多，已停止，请换个问法或分步提问。")


if __name__ == "__main__":
    run()
