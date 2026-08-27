"""ScriptWriter Agent — 视频剧本与分镜创作

使用本地推理 API（llama.cpp + Qwen）生成完整视频剧本，
包括：剧情文案、分镜拆分、文生图提示词、图生视频提示词、字幕等。

输出格式：参考 models/project.py 中的 Project / Scene 数据模型。
"""

import json
import logging
import sys
import os
from datetime import datetime
from typing import Optional

# 确保项目根目录在路径中
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from services.llm_client import LLMClient
from models.project import (
    Project, Scene, VideoConfig, TaskStatus,
    VideoRatio, VideoStyle,
)

logger = logging.getLogger(__name__)

# ============================================================
# 风格 → Prompt 修饰词映射
# ============================================================
STYLE_PROMPT_MAP = {
    VideoStyle.REALISTIC: {
        "t2i_tags": "photorealistic, hyper-realistic, 8K, natural lighting, DSLR, shallow depth of field, National Geographic style, detailed texture",
        "i2v_tags": "cinematic motion, natural camera movement, realistic physics, smooth transition",
    },
    VideoStyle.ANIMATION: {
        "t2i_tags": "animation style, cel shading, vibrant colors, smooth gradients, Disney/Pixar inspired, whimsical",
        "i2v_tags": "cartoon motion, smooth animation, playful movement, whimsical flow",
    },
    VideoStyle.ANIME: {
        "t2i_tags": "anime style, Japanese anime, vibrant palette, detailed background, character focus, Studio Ghibli inspired, Makoto Shinkai style",
        "i2v_tags": "anime motion, gentle camera pan, dynamic scene flow, emotional atmosphere",
    },
    VideoStyle.STYLE_3D: {
        "t2i_tags": "3D render, Octane render, Unreal Engine 5, ray tracing, subsurface scattering, volumetric lighting, hyper-realistic 3D",
        "i2v_tags": "3D camera flythrough, cinematic 3D motion, smooth tracking shot",
    },
    VideoStyle.CYBERPUNK: {
        "t2i_tags": "cyberpunk, neon lights, rain reflections, dark urban night, holographic displays, Blade Runner aesthetic, synthwave vibes, high contrast",
        "i2v_tags": "slow cinematic pan, neon light flicker, rain falling, atmospheric haze movement",
    },
    VideoStyle.INK_WASH: {
        "t2i_tags": "Chinese ink wash painting, sumi-e, brush strokes, zen aesthetic, minimalist, monochrome with color accents, rice paper texture",
        "i2v_tags": "ink flowing in water, gentle brush stroke animation, slow dissolve, poetic motion",
    },
    VideoStyle.PIXEL: {
        "t2i_tags": "pixel art, retro game style, 8-bit aesthetic, chiptune vibe, blocky pixels, limited color palette, nostalgic",
        "i2v_tags": "retro game camera, pixel scrolling, simple frame-by-frame animation",
    },
    VideoStyle.OIL_PAINTING: {
        "t2i_tags": "oil painting, impasto technique, visible brush strokes, canvas texture, Van Gogh style, rich colors, thick paint application",
        "i2v_tags": "painting-like motion, slow morphing brush strokes, artistic transition",
    },
}

# ============================================================
# 系统 Prompt（核心）
# ============================================================
SYSTEM_PROMPT = """你是一个专业的视频编剧和分镜师。你的任务是根据用户输入的主题和配置，生成完整的视频剧本。

你必须输出严格的 JSON 格式。输出内容必须包含：
- title: 视频标题（字符串）
- summary: 一句话简介（字符串）
- scenes: 分镜数组，每个分镜包含：
  - scene_id: 分镜编号（整数，从1开始）
  - duration: 时长（整数，秒）
  - description: 画面描述（中文，详细描述构图、色调、人物、环境等）
  - narration: 配音文本（中文，口语化，用于朗读）
  - subtitle: 字幕文本（与 narration 保持一致，后端会强制对齐）
  - t2i_prompt: 文生图提示词（英文，包含详细视觉描述、风格和质量标签，不含文字内容）
  - i2v_prompt: 图生视频提示词（英文，描述运镜和动作）
  - camera: 镜头语言（如：远景/近景/推/拉/摇/移）

创作要求：
1. 每个分镜的 duration 加起来应接近目标视频总时长
2. t2i_prompt 用英文写，包含详细的视觉描述 + 风格标签 + 质量标签
3. i2v_prompt 用英文写，描述运镜方向、动作幅度、氛围变化
4. narration 和 subtitle 用中文，简洁口语化
5. 分镜之间要有叙事连贯性
6. t2i_prompt 不要包含文字/字符内容
7. 所有 prompt 要避免负面内容（no deformed, no blurry, etc.）

重要：只输出 JSON，不要包含任何说明文字或代码块标记。"""


class ScriptWriter:
    """剧本创作 Agent"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def generate(
        self,
        topic: str,
        config: VideoConfig,
        project_id: str = "",
    ) -> Project:
        """根据主题和配置生成完整视频剧本

        Args:
            topic: 视频主题（如"中国茶文化宣传片"）
            config: 视频配置（比例、分辨率、风格等）
            project_id: 项目ID，不传则自动生成

        Returns:
            Project: 包含分镜列表的项目对象
        """
        ratio_desc = self._ratio_description(config.ratio)
        style_tags = self._get_style_tags(config.style)

        # JSON schema 说明（不给出具体示例，防止模型复制占位文本）
        schema_desc = """{
  "title": "视频标题（字符串）",
  "summary": "一句话简介（字符串）",
  "scenes": [
    {
      "scene_id": "整数序号1",
      "duration": "整数秒数",
      "description": "详细画面描述（中文）",
      "narration": "配音文本（中文）",
      "subtitle": "字幕文本（与 narration 一致，后端强制对齐）",
      "t2i_prompt": "文生图提示词（英文）",
      "i2v_prompt": "图生视频提示词（英文）",
      "camera": "镜头语言"
    }
  ]
}"""

        user_prompt = f"""请为以下视频主题创作一个完整的剧本。

【主题】{topic}
【视频风格】{config.style.value}
【画面比例】{ratio_desc}
【目标时长】约 {config.target_duration} 秒
【分镜数量】必须恰好输出 {config.scene_count} 个分镜
【镜头语言】需包含各种景别（远景、中景、近景、特写）和运镜（推、拉、摇、移）

【风格提示词参考】
t2i 风格标签: {style_tags['t2i_tags']}
i2v 风格标签: {style_tags['i2v_tags']}

请严格按照以下 JSON 结构输出，字段说明在注释中：
{schema_desc}

要求：
1. scenes 数组必须有且仅有 {config.scene_count} 个元素
2. 每个分镜的 description、narration 必须是具体的内容，不能是字段说明文字
3. t2i_prompt 和 i2v_prompt 用英文
4. narration 和 subtitle 用中文
5. duration 是整数秒，所有 duration 之和接近 {config.target_duration}
6. 只输出 JSON，不要额外文字或 markdown 格式
7. 重要：输出的 JSON 中每个字段的值必须是真实内容，不能是"配音文本"、"画面描述"这类说明文字"""

        # 重试机制：最多尝试 3 次
        max_retries = 4
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"🎬 ScriptWriter 开始创作: 「{topic}」(尝试 {attempt+1}/{max_retries})")

                raw = self.llm.chat(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,  # 低温度确保一致性
                    max_tokens=8192,
                )

                # 解析 JSON
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as e:
                    last_error = f"JSON 解析失败: {e}"
                    logger.warning(f"  ⚠️ 尝试 {attempt+1}: {last_error}")
                    continue

                # 检查 scenes 是否存在
                raw_scenes = data.get("scenes", [])
                if not raw_scenes or len(raw_scenes) == 0:
                    last_error = "模型返回的 scenes 为空"
                    logger.warning(f"  ⚠️ 尝试 {attempt+1}: {last_error}")
                    continue

                # 检查是否复制了模板（占位文本特征）
                template_indicators = [
                    "配音文本", "画面描述", "旁白", "字幕文本",
                    "文生图提示词", "图生视频提示词", "镜头语言",
                    "t2i_prompt", "i2v_prompt",
                ]
                template_copy = False
                for s in raw_scenes:
                    desc = str(s.get("description", ""))
                    if any(indicator in desc for indicator in template_indicators):
                        template_copy = True
                        break

                if template_copy:
                    last_error = "模型复制了模板占位文本，未生成真实内容"
                    logger.warning(f"  ⚠️ 尝试 {attempt+1}: {last_error}")
                    continue

                # 检查分镜数量是否接近目标
                if len(raw_scenes) < config.scene_count:
                    last_error = f"分镜数量不足: {len(raw_scenes)} < {config.scene_count}"
                    logger.warning(f"  ⚠️ 尝试 {attempt+1}: {last_error}")
                    continue

                # 检查 scenes 格式
                valid_scenes = []
                for i, s in enumerate(raw_scenes):
                    if not isinstance(s, dict):
                        continue
                    # 兼容不同 key 命名风格
                    scene_id = s.get("scene_id") or s.get("id") or (i + 1)
                    duration = s.get("duration", 5)
                    if isinstance(duration, str):
                        duration = int(duration.replace("秒", "").strip())
                    valid_scenes.append(Scene(
                        scene_id=int(scene_id),
                        duration=int(duration),
                        description=s.get("description", "") or s.get("visual", "") or str(s),
                        narration=s.get("narration", "") or s.get("audio", "").replace("旁白：", "").replace("旁白:", "").strip(),
                        # V2.2 决策：字幕 = 旁白（一字不差），不再由 LLM 单独生成精简版
                        subtitle=s.get("narration", "") or s.get("audio", "").replace("旁白：", "").replace("旁白:", "").strip(),
                        t2i_prompt=self._enrich_t2i_prompt(
                            s.get("t2i_prompt", "") or s.get("t2i", "") or s.get("visual", ""),
                            config.style, style_tags,
                        ),
                        i2v_prompt=self._enrich_i2v_prompt(
                            s.get("i2v_prompt", "") or s.get("i2v", "") or "",
                            config.style, style_tags,
                        ),
                        camera=s.get("camera", "") or s.get("镜头", "中景"),
                    ))

                if not valid_scenes:
                    last_error = "所有分镜格式无效"
                    logger.warning(f"  ⚠️ 尝试 {attempt+1}: {last_error}")
                    continue

                # 成功！构建 Project
                now = datetime.now().strftime("%Y%m%d_%H%M%S")
                pid = project_id or f"proj_{now}"

                project = Project(
                    project_id=pid,
                    name=data.get("title", topic),
                    topic=topic,
                    config=config,
                    scenes=valid_scenes,
                    created_at=datetime.now().isoformat(),
                    status=TaskStatus.COMPLETED,
                )

                total_duration = sum(s.duration for s in valid_scenes)
                logger.info(f"  ✅ 剧本完成: 「{project.name}」{len(valid_scenes)}个分镜, {total_duration}s")
                return project

            except Exception as e:
                last_error = str(e)
                logger.warning(f"  ⚠️ 尝试 {attempt+1} 失败: {e}")
                continue

        # 所有重试都失败
        raise RuntimeError(
            f"ScriptWriter 在 {max_retries} 次尝试后仍无法生成有效剧本。"
            f"最后错误: {last_error}"
        )

    def _ratio_description(self, ratio: VideoRatio) -> str:
        map = {
            VideoRatio.R16_9: "横屏 16:9（宽幅电影感）",
            VideoRatio.R9_16: "竖屏 9:16（手机短视频风格）",
            VideoRatio.R1_1: "方形 1:1（社交媒体风格）",
        }
        return map.get(ratio, "16:9")

    def _get_style_tags(self, style: VideoStyle) -> dict:
        """获取风格对应的提示词修饰标签"""
        return STYLE_PROMPT_MAP.get(style, STYLE_PROMPT_MAP[VideoStyle.REALISTIC])

    def _enrich_t2i_prompt(self, prompt: str, style: VideoStyle, tags: dict) -> str:
        """用风格标签增强文生图提示词"""
        prompt = prompt.strip().rstrip(".,")
        return f"{prompt}, {tags['t2i_tags']}"

    def _enrich_i2v_prompt(self, prompt: str, style: VideoStyle, tags: dict) -> str:
        """用风格标签增强图生视频提示词"""
        prompt = prompt.strip().rstrip(".,")
        return f"{prompt}, {tags['i2v_tags']}"
