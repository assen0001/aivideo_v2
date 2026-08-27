"""LLM 客户端 - 调用 llama.cpp + Qwen 推理 API（V2.0 参数化）

构造函数支持显式传参（GenerationManager 按 config_snapshot 注入）；
参数为 None 时从 settings 表读取兜底（兼容 test/ 脚本直接 LLMClient()）。
"""

import json
import logging
import re
from typing import Optional
import requests

from services.db import get_setting

logger = logging.getLogger(__name__)


class LLMClient:
    """与 llama.cpp Qwen 推理服务通信的客户端

    注意：Qwen 推理模型输出可能分布在 reasoning_content / content 字段，
    通过正则从末尾提取 JSON 结果。
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        # 参数未显式传入时，从 settings 表兜底（本地单用户默认值）
        self.api_base = (api_base or get_setting("llm_api_base", "")).rstrip("/")
        self.api_key = api_key or get_setting("llm_api_key", "")
        self.model = model or get_setting("llm_model", "")
        self.timeout = int(timeout or get_setting("llm_timeout", "300") or 300)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })

    def chat(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
    ) -> str:
        """发送对话请求，返回模型输出的文本内容"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            resp = self.session.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"LLM API 请求超时 ({self.timeout}s)")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM API 请求失败: {e}")
        except json.JSONDecodeError:
            raise RuntimeError("LLM API 返回非 JSON 响应")

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        reasoning = message.get("reasoning_content", "") or ""
        content = message.get("content", "") or ""
        full_text = (reasoning.strip() + "\n" + content.strip()).strip()
        if not full_text:
            raise RuntimeError(f"模型返回为空 (finish_reason={choice.get('finish_reason')})")

        return self._clean_markdown_json(full_text)

    def _clean_markdown_json(self, text: str) -> str:
        """从模型输出中提取纯 JSON 文本"""
        text = text.strip()

        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        json_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
        for block in reversed(json_blocks):
            candidate = block.strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                try:
                    merged = self._merge_scattered_jsons(candidate)
                    if merged:
                        return merged
                except Exception:
                    pass

        for end_pos in range(len(text), 0, -1):
            try:
                candidate = text[max(0, end_pos - 4096):end_pos]
                json.loads(f"[{candidate}]" if not candidate.startswith("[") else candidate)
                last_brace = candidate.rfind("{")
                if last_brace >= 0:
                    return candidate[last_brace:]
            except Exception:
                continue

        merged = self._merge_scattered_jsons(text)
        if merged:
            return merged

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs[-1] if paragraphs else text

    def _merge_scattered_jsons(self, text: str) -> str:
        """合并文本中所有零散的 JSON 对象为数组"""
        objects = []
        i = 0
        while i < len(text):
            start = text.find("{", i)
            if start < 0:
                break
            depth = 0
            for j in range(start, len(text)):
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:j + 1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                objects.append(obj)
                        except Exception:
                            pass
                        i = j + 1
                        break
            else:
                i = start + 1

        if len(objects) >= 1:
            if len(objects) == 1 and "scenes" in objects[0]:
                return json.dumps(objects[0], ensure_ascii=False)
            if any("scene_id" in o or "id" in o or "duration" in o for o in objects):
                merged = {"title": "自动合成", "scenes": objects}
                return json.dumps(merged, ensure_ascii=False)
            return json.dumps(objects[-1], ensure_ascii=False)

        return ""

    def chat_json(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """调用 LLM 并确保返回 JSON 对象"""
        text = self.chat(
            messages=[
                {"role": "system", "content": messages[0]["content"] + "\n\n你只能输出纯 JSON 格式，不要包含 ```json 标记。确保 JSON 语法正确。"}
            ] + messages[1:],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}\n原始文本: {text[:500]}")
            raise ValueError(f"模型返回非有效 JSON: {e}")
