"""ImageCreator Agent — 文生图

读取 ScriptWriter 生成的剧本中的每个分镜，调用 ComfyUI z-image-turbo
生成分镜图片。支持并行生成。
"""

import json
import logging
import os
import sys
from typing import Callable, Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from services.comfyui_img import ComfyUIImgClient
from models.project import (
    Project, Scene, TaskStatus, VideoResolution, VideoRatio,
)

logger = logging.getLogger(__name__)

# ============================================================
# 分辨率映射
# ============================================================
RESOLUTION_MAP = {
    # 16:9 横屏
    (VideoRatio.R16_9, VideoResolution.SD_640_LANDSCAPE): (640, 360),
    (VideoRatio.R16_9, VideoResolution.HD_1280_LANDSCAPE): (1280, 720),
    (VideoRatio.R16_9, VideoResolution.UHD_1920_LANDSCAPE): (1920, 1080),
    # 9:16 竖屏
    (VideoRatio.R9_16, VideoResolution.SD_640_PORTRAIT): (360, 640),
    (VideoRatio.R9_16, VideoResolution.HD_1280_PORTRAIT): (720, 1280),
    (VideoRatio.R9_16, VideoResolution.UHD_1920_PORTRAIT): (1080, 1920),
    # 1:1 方形
    (VideoRatio.R1_1, VideoResolution.SD_640_LANDSCAPE): (512, 512),
    (VideoRatio.R1_1, VideoResolution.HD_1280_LANDSCAPE): (768, 768),
    (VideoRatio.R1_1, VideoResolution.UHD_1920_LANDSCAPE): (1024, 1024),
}

# 默认分辨率（16:9 高清）
DEFAULT_RESOLUTION = (640, 360)

# 最大并行数（受显存限制，串行生成更稳定）
MAX_PARALLEL = 1


class ImageCreator:
    """图片生成 Agent — 调用 ComfyUI z-image-turbo"""

    def __init__(self, comfyui: Optional[ComfyUIImgClient] = None):
        self.comfyui = comfyui or ComfyUIImgClient()

    def generate_scenes(
        self,
        project: Project,
        output_base: str = "./output",
        on_scene_done: Optional[Callable[[Scene], None]] = None,
    ) -> Project:
        """生成项目中所有分镜的图片

        Args:
            project: 包含分镜列表的项目对象
            output_base: 输出根目录
            on_scene_done: 可选回调，每完成一个分镜（成功/失败均触发）后调用，
                用于分镜级实时写库（前端轮询可见）。

        Returns:
            Project: 更新了 image_path 的项目对象
        """
        image_dir = os.path.join(output_base, project.project_id, "images")
        os.makedirs(image_dir, exist_ok=True)

        # 获取分辨率
        width, height = RESOLUTION_MAP.get(
            (project.config.ratio, project.config.resolution),
            DEFAULT_RESOLUTION,
        )

        total = len(project.scenes)
        logger.info(f"🎨 ImageCreator: 开始生成 {total} 个分镜图片 ({width}×{height})")

        for i, scene in enumerate(project.scenes):
            scene.status = TaskStatus.IN_PROGRESS
            logger.info(f"  [{i+1}/{total}] 分镜{scene.scene_id}: 生成中...")

            try:
                images = self.comfyui.generate_t2i(
                    prompt=scene.t2i_prompt,
                    width=width,
                    height=height,
                    output_dir=image_dir,
                )

                if images:
                    # 重命名为 scene_{id}.png
                    src = images[0]
                    dst = os.path.join(image_dir, f"scene_{scene.scene_id:03d}.png")
                    if src != dst:
                        os.rename(src, dst)
                    scene.image_path = dst
                    scene.status = TaskStatus.COMPLETED
                    logger.info(f"  ✅ 分镜{scene.scene_id} → {dst}")
                else:
                    scene.status = TaskStatus.FAILED
                    logger.error(f"  ❌ 分镜{scene.scene_id}: 未生成图片")

            except Exception as e:
                scene.status = TaskStatus.FAILED
                logger.error(f"  ❌ 分镜{scene.scene_id}: {e}")

            # 分镜级写库回调：成功/失败均写入，前端轮询即时可见（回调异常不影响生成流程）
            if on_scene_done:
                try:
                    on_scene_done(scene)
                except Exception as e:
                    logger.error(f"  ⚠️ 分镜{scene.scene_id} 写库回调异常: {e}")

        # 统计
        success = sum(1 for s in project.scenes if s.status == TaskStatus.COMPLETED)
        failed = sum(1 for s in project.scenes if s.status == TaskStatus.FAILED)
        logger.info(f"📊 ImageCreator 完成: {success}成功, {failed}失败 / {total}总")

        return project
