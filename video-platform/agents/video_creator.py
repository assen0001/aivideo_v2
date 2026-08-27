"""VideoCreator Agent — 图生视频

读取 ImageCreator 生成的分镜图片，调用 ComfyUI Wan2.2 I2V
生成每个分镜的短视频片段。
"""

import json
import logging
import math
import os
import sys
import time
from typing import Callable, Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from services.comfyui_vid import ComfyUIVidClient
from models.project import Project, Scene, TaskStatus

logger = logging.getLogger(__name__)

# ============================================================
# 帧数计算（V2.4 语音驱动 + 5 秒硬上限）
# ============================================================
# duration: 分镜视频目标时长（秒），有配音时取分镜语音真实时长，否则取 scenes.duration，兜底 4 秒
# 帧数 = min(5*fps+1, ceil((duration + 0.3) * fps))：+0.3s 语音收口缓冲；超 5 秒视频质量差，封顶
def calc_frames(fps: int, duration: float) -> int:
    max_fps = 5 * fps + 1
    return min(max_fps, math.ceil((duration + 0.3) * fps))


# 分辨率映射（与 ImageCreator 同步）
# 格式：(视频比例, 分辨率值) -> (宽度, 高度)
RESOLUTION_MAP = {
    # 16:9 横屏
    ("16:9", "普清360p 横屏"): (640, 360),
    ("16:9", "高清720p 横屏"): (1280, 720),
    ("16:9", "超清1080p 横屏"): (1920, 1080),
    # 9:16 竖屏
    ("9:16", "普清360p 竖屏"): (360, 640),
    ("9:16", "高清720p 竖屏"): (720, 1280),
    ("9:16", "超清1080p 竖屏"): (1080, 1920),
    # 1:1 方形
    ("1:1", "普清360p 横屏"): (360, 360),  # 方形时取较小的边
    ("1:1", "高清720p 横屏"): (720, 720),
    ("1:1", "超清1080p 横屏"): (1080, 1080),
}


class VideoCreator:
    """视频生成 Agent — 调用 ComfyUI Wan2.2 I2V"""

    def __init__(self, comfyui: Optional[ComfyUIVidClient] = None):
        self.comfyui = comfyui or ComfyUIVidClient()

    def generate_scenes(
        self,
        project: Project,
        output_base: str = "./output",
        on_scene_done: Optional[Callable[[Scene], None]] = None,
    ) -> Project:
        """生成项目中所有分镜的视频片段

        Args:
            project: 包含分镜列表（需已有 image_path）的项目对象
            output_base: 输出根目录
            on_scene_done: 可选回调，每完成一个分镜（成功/失败均触发）后调用，
                用于分镜级实时写库（前端轮询可见）。

        Returns:
            Project: 更新了 video_path 的项目对象
        """
        video_dir = os.path.join(output_base, project.project_id, "videos")
        os.makedirs(video_dir, exist_ok=True)

        # 分辨率
        key = (project.config.ratio.value, project.config.resolution.value)
        width, height = RESOLUTION_MAP.get(key, (640, 360))
        fps = project.config.fps

        # 只处理有图片且未生成视频的分镜
        to_generate = [
            s for s in project.scenes
            if s.image_path and os.path.exists(s.image_path)
            and not s.video_path  # 尚未生成视频（status 可能已被 ImageCreator 设为 COMPLETED）
        ]

        total = len(to_generate)
        logger.info(f"🎞️ VideoCreator: 开始生成 {total} 个分镜视频 ({width}×{height} @{fps}fps)")

        for i, scene in enumerate(to_generate):
            scene.status = TaskStatus.IN_PROGRESS
            # V2.4：优先取分镜语音真实时长；无配音/语音失败回退 scenes.duration；再兜底 4 秒
            dur = scene.voice_duration or scene.duration or 4
            frames = calc_frames(fps, dur)
            logger.info(f"  [{i+1}/{total}] 分镜{scene.scene_id}: {frames}帧, 目标时长{dur}s")

            try:
                videos = self.comfyui.generate_i2v(
                    image_path=scene.image_path,
                    prompt=scene.i2v_prompt,
                    width=width,
                    height=height,
                    length=frames,
                    fps=fps,
                    output_dir=video_dir,
                )

                if videos:
                    # 等待文件完全写入（避免竞态条件）
                    src = videos[0]
                    max_wait = 30
                    waited = 0
                    while not os.path.exists(src) and waited < max_wait:
                        time.sleep(1)
                        waited += 1

                    if not os.path.exists(src):
                        scene.status = TaskStatus.FAILED
                        logger.error(f"  ❌ 分镜{scene.scene_id}: 文件未生成 {src}")
                        continue

                    # 等待文件写入完成（检查文件大小是否稳定）
                    stable_size = -1
                    stable_count = 0
                    for _ in range(10):
                        try:
                            current_size = os.path.getsize(src)
                            if current_size == stable_size:
                                stable_count += 1
                                if stable_count >= 3:
                                    break
                            else:
                                stable_size = current_size
                                stable_count = 0
                        except OSError:
                            pass
                        time.sleep(1)

                    # 重命名
                    dst = os.path.join(video_dir, f"scene_{scene.scene_id:03d}.mp4")
                    if src != dst:
                        os.rename(src, dst)
                    scene.video_path = dst
                    scene.status = TaskStatus.COMPLETED
                    logger.info(f"  ✅ 分镜{scene.scene_id} → {dst} ({os.path.getsize(dst)/1024/1024:.1f} MB)")
                else:
                    scene.status = TaskStatus.FAILED
                    logger.error(f"  ❌ 分镜{scene.scene_id}: 未生成视频")

            except Exception as e:
                scene.status = TaskStatus.FAILED
                logger.error(f"  ❌ 分镜{scene.scene_id}: {e}")

            # 分镜级写库回调：成功/失败均写入（回调异常不影响生成流程）
            if on_scene_done:
                try:
                    on_scene_done(scene)
                except Exception as e:
                    logger.error(f"  ⚠️ 分镜{scene.scene_id} 写库回调异常: {e}")

            # 每次生成后释放显存（Wan2.2 很吃显存）
            try:
                self.comfyui.free_memory()
            except Exception:
                pass

        success = sum(1 for s in project.scenes if s.status == TaskStatus.COMPLETED and s.video_path)
        failed = sum(1 for s in project.scenes if s.status == TaskStatus.FAILED)
        logger.info(f"📊 VideoCreator 完成: {success}成功, {failed}失败")

        return project
