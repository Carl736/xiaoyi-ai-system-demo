# app/service/agent_service.py
import json
from openai import OpenAI
from app.config import settings

client = OpenAI(
    api_key=settings.settings.deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)


def should_search_textbook(question: str) -> dict:
    """
    让大模型判断：用户问题是否需要搜索教材。

    返回：
        {
            "need_search": True/False,
            "reason": "判断理由"
        }
    """

    prompt = f"""
你是一个智能路由助手。判断用户问题是否与"教材知识库"相关。

判断规则：
- 需要搜教材：用户问数学公式、定理证明、概念解释、教材章节、例题详解等
- 不需要搜教材：用户问天气、问候、个人情况、与学习无关的闲聊

用户问题：{question}

只回复 JSON，格式如下：
{{"need_search": true/false, "reason": "简短判断理由"}}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        # 兜底：解析失败时默认搜教材
        return {
            "need_search": True,
            "reason": f"决策解析失败，默认搜教材：{e}"
        }