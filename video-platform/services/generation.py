"""生成管线编排 — GenerationManager（V2.0 核心）

职责：
- 全局单并发锁：同一时间仅允许 1 个项目处于「进行中」
- 从 projects.config_snapshot 构建 5 个客户端/Agent（Agent 不直读 settings）
- 五步执行 + 每步写库（短事务）：script → images → videos → voice → compose
- 进度维护：_progress[project_id] = {"step","progress","error"}
- 停止机制：request_stop 设 Event，客户端在长循环（poll/批处理）检查并中断

写库时机（需求 §3.2 / 设计 §3.1，V2.1 分镜级实时写库）：
  script  → status=进行中 + scene_count + upsert_scenes
  images  → 每分镜 on_scene_done→upsert_scene（实时）；step 末尾 upsert_scenes 兜底补齐
  videos  → 每分镜 on_scene_done→upsert_scene（实时）；step 末尾 upsert_scenes 兜底补齐
  voice   → 每分镜 on_scene_done→upsert_scene（实时）；step 末尾 upsert_scenes 兜底补齐
            V2.3：仅生成逐镜语音，不再合成 voiceover.wav 全片配音；audio_path 置空
  compose → status=完成 + final_video_url（V2.3：逐镜 max 对齐后直接拼接，不混全片配音）
  失败    → status=失败 + error_msg
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from services import db
from services.llm_client import LLMClient
from services.comfyui_img import ComfyUIImgClient
from services.comfyui_vid import ComfyUIVidClient
from services.voice_actor import VoiceActor
from services.ffmpeg_utils import get_ffmpeg_path
from services.stop_flag import StopGeneration
from agents.script_writer import ScriptWriter
from agents.image_creator import ImageCreator
from agents.video_creator import VideoCreator
from agents.video_composer import VideoComposer
from models.project import (
    Project, Scene, VideoConfig, TaskStatus,
    VideoRatio, VideoResolution, VideoStyle, VoiceStyle,
)

logger = logging.getLogger(__name__)

# 进度映射（V2.4：voice 前置，script=5 voice=20 images=35 videos=60 compose=85 done=100）
STEP_PROGRESS = {
    "script": 5,
    "voice": 20,
    "images": 35,
    "videos": 60,
    "compose": 85,
    "done": 100,
}

# scenes.status 枚举映射（TaskStatus → scenes 表枚举，§9）
_SCENE_STATUS_MAP = {
    "等待": "待生成",
    "进行中": "生成中",
    "完成": "完成",
    "失败": "失败",
}


def _scene_to_row(scene: Scene, project_id: str) -> Dict[str, Any]:
    """Scene 内存对象 → scenes 表行（路径转相对项目根）"""
    status = scene.status.value if hasattr(scene.status, "value") else str(scene.status)
    return {
        "project_id": project_id,
        "scene_no": int(scene.scene_id),
        "duration": float(scene.duration or 5),
        "description": scene.description or "",
        "narration": scene.narration or "",
        "subtitle": scene.subtitle or "",
        "t2i_prompt": scene.t2i_prompt or "",
        "i2v_prompt": scene.i2v_prompt or "",
        "camera": scene.camera or "",
        "image_url": db.relpath_of(scene.image_path),
        "video_url": db.relpath_of(scene.video_path),
        "voice_path": db.relpath_of(scene.voice_path),
        "voice_duration": float(scene.voice_duration or 0),
        "status": _SCENE_STATUS_MAP.get(status, status),
    }


# scenes 表 status → TaskStatus（_SCENE_STATUS_MAP 反向，recompose 重建内存对象用）
_DB_SCENE_STATUS_MAP = {
    "待生成": TaskStatus.PENDING,
    "生成中": TaskStatus.IN_PROGRESS,
    "完成": TaskStatus.COMPLETED,
    "失败": TaskStatus.FAILED,
}


def _db_row_to_scene(row: Dict[str, Any]) -> Scene:
    """scenes 表行 → Scene 内存对象（DB 相对项目根路径 → 绝对路径，供 compose 复用）"""
    db_status = row.get("status", "待生成")
    return Scene(
        scene_id=int(row["scene_no"]),
        duration=int(row.get("duration") or 5),
        description=row.get("description", ""),
        narration=row.get("narration", ""),
        subtitle=row.get("subtitle", ""),
        t2i_prompt=row.get("t2i_prompt", ""),
        i2v_prompt=row.get("i2v_prompt", ""),
        camera=row.get("camera", ""),
        image_path=str(db.PROJECT_ROOT / row["image_url"]) if row.get("image_url") else None,
        video_path=str(db.PROJECT_ROOT / row["video_url"]) if row.get("video_url") else None,
        voice_path=str(db.PROJECT_ROOT / row["voice_path"]) if row.get("voice_path") else None,
        voice_duration=float(row.get("voice_duration") or 0) or None,
        status=_DB_SCENE_STATUS_MAP.get(db_status, TaskStatus.PENDING),
    )


def _build_video_config(snap_vc: Dict[str, Any]) -> VideoConfig:
    """从 config_snapshot 的 video_config 构建 VideoConfig"""
    # V2.4：voice 可能为 "none"（无配音），需容错转换；V2.5：历史中文值回退 NONE
    voice_val = snap_vc.get("voice", "none")
    try:
        voice = VoiceStyle(voice_val)
    except ValueError:
        voice = VoiceStyle.NONE
    return VideoConfig(
        ratio=VideoRatio(snap_vc.get("ratio", "16:9")),
        resolution=VideoResolution(snap_vc.get("resolution", "普清360p 横屏")),
        fps=int(snap_vc.get("fps", 16)),
        style=VideoStyle(snap_vc.get("style", "写实")),
        voice=voice,
        target_duration=int(snap_vc.get("target_duration", 30)),
        scene_count=int(snap_vc.get("scene_count", 5)),
    )


class GenerationManager:
    """生成管线管理器：单并发锁 + 进度 + 后台线程执行体"""

    _lock = threading.Lock()
    _current: Optional[str] = None
    _progress: Dict[str, Dict[str, Any]] = {}
    _stop_events: Dict[str, threading.Event] = {}

    # ---- 单并发锁 ----

    @classmethod
    def try_start(cls, project_id: str) -> bool:
        """非阻塞尝试获取全局锁；成功记录 _current"""
        if cls._lock.acquire(blocking=False):
            cls._current = project_id
            cls._progress[project_id] = {"step": "script", "progress": STEP_PROGRESS["script"], "error": ""}
            cls._stop_events.pop(project_id, None)
            return True
        return False

    @classmethod
    def release(cls, project_id: str) -> None:
        """释放锁 + 清 _current（finally 中调用）"""
        try:
            if cls._current == project_id:
                cls._current = None
            cls._progress.pop(project_id, None)
            cls._stop_events.pop(project_id, None)
        finally:
            try:
                cls._lock.release()
            except RuntimeError:
                pass

    @classmethod
    def get_progress(cls, project_id: str) -> Dict[str, Any]:
        """读取内存进度（仅进行中时有值；非进行中返回空 dict）"""
        return dict(cls._progress.get(project_id, {}))

    @classmethod
    def is_busy(cls) -> bool:
        """当前是否有项目在创作中"""
        return cls._current is not None

    @classmethod
    def current_project_id(cls) -> Optional[str]:
        return cls._current

    # ---- 停止生成（用户主动中断）----

    @classmethod
    def request_stop(cls, project_id: str) -> bool:
        """请求停止项目生成。仅允许停止当前正在进行中的项目。

        设置 stop Event 后立即返回（不阻塞）。后台线程在下一个检查点
        （step 边界 / 客户端长循环）检测到 Event，抛 StopGeneration 退出。
        """
        if cls._current != project_id:
            return False
        ev = cls._stop_events.get(project_id)
        if ev is None:
            ev = threading.Event()
            cls._stop_events[project_id] = ev
        if not ev.is_set():
            ev.set()
            logger.info(f"[{project_id}] 已收到停止请求")
        return True

    @classmethod
    def is_stop_requested(cls, project_id: str) -> bool:
        """检查该项目是否已请求停止"""
        ev = cls._stop_events.get(project_id)
        return bool(ev and ev.is_set())

    @classmethod
    def _check_stop(cls, project_id: str) -> None:
        """若已请求停止则抛 StopGeneration。各 step 前/长循环内调用。"""
        if cls.is_stop_requested(project_id):
            raise StopGeneration("用户停止生成")

    @classmethod
    def _set_progress(cls, project_id: str, step: str, progress: int, error: str = "") -> None:
        cls._progress[project_id] = {"step": step, "progress": progress, "error": error}

    @classmethod
    def run(cls, project_id: str) -> None:
        """后台线程执行体：读 config_snapshot → 构建客户端 → 五步 + 写库"""
        try:
            row = db.get_project(project_id)
            if not row:
                raise RuntimeError(f"项目不存在: {project_id}")

            try:
                snap = json.loads(row.get("config_snapshot") or "{}")
            except json.JSONDecodeError:
                snap = {}
            if not isinstance(snap, dict):
                snap = {}

            video_config = _build_video_config(snap.get("video_config", {}))

            # 按快照构建 5 个客户端/Agent（D6：每次生成新建，进行中任务保持旧参数）
            # stop_check 回调：传给 ComfyUI 客户端（polling 阶段最耗时，是 stop 主战场）
            stop_check: Callable[[], None] = lambda: cls._check_stop(project_id)
            llm = LLMClient(**snap.get("llm", {}))
            t2i = ComfyUIImgClient(stop_check=stop_check, **snap.get("t2i", {}))
            i2v = ComfyUIVidClient(stop_check=stop_check, **snap.get("i2v", {}))
            voice = VoiceActor(**snap.get("tts", {}))
            composer = VideoComposer(ffmpeg_path=get_ffmpeg_path())

            sw = ScriptWriter(llm_client=llm)
            ic = ImageCreator(comfyui=t2i)
            vc = VideoCreator(comfyui=i2v)

            output_base = str(db.OUTPUT_DIR)  # D:\aivideo_v2\output（绝对路径，Agent 写文件用）

            # 分镜级写库回调：每完成一个分镜产物立即写库，前端 3s 轮询即可看到该分镜。
            # 回调异常只记日志，绝不影响生成主流程；step 末尾仍保留全量 upsert_scenes 兜底补齐。
            def on_scene_done(scene: Scene) -> None:
                try:
                    db.upsert_scene(project_id, _scene_to_row(scene, project_id))
                except Exception:
                    logger.exception(f"[{project_id}] 分镜{scene.scene_id} 写库失败（不影响生成）")

            # ========== Step 1: script ==========
            cls._set_progress(project_id, "script", STEP_PROGRESS["script"])
            cls._check_stop(project_id)
            logger.info(f"[{project_id}] Step 1: ScriptWriter")
            project = sw.generate(row.get("topic", ""), video_config, project_id)
            db.update_project_status(project_id, "进行中")
            db.update_project_scene_count(project_id, len(project.scenes))
            db.upsert_scenes(project_id, [_scene_to_row(s, project_id) for s in project.scenes])

            # ========== Step 2: voice（V2.4 前置到文生图之前；无配音时跳过）==========
            if video_config.voice != VoiceStyle.NONE:
                cls._set_progress(project_id, "voice", STEP_PROGRESS["voice"])
                cls._check_stop(project_id)
                logger.info(f"[{project_id}] Step 2: VoiceActor (IndexTTS)")
                # V2.3: 只生成逐镜语音（scene_{n}.wav），不再合成全片配音；audio_path 保留字段但置空
                voice.generate_project_audio(project, output_base, on_scene_done=on_scene_done)
                project.audio_path = None
                db.upsert_scenes(project_id, [_scene_to_row(s, project_id) for s in project.scenes])

                total_voice_dur = sum(s.voice_duration or 0 for s in project.scenes)
                logger.info(f"[{project_id}] 配音完成: 总语音时长 {total_voice_dur:.1f}s")
            else:
                logger.info(f"[{project_id}] Step 2: 跳过语音合成（无配音），分镜视频时长由 scenes.duration 决定")

            # ========== Step 3: images ==========
            cls._set_progress(project_id, "images", STEP_PROGRESS["images"])
            cls._check_stop(project_id)
            logger.info(f"[{project_id}] Step 3: ImageCreator")
            project = ic.generate_scenes(project, output_base, on_scene_done=on_scene_done)
            db.upsert_scenes(project_id, [_scene_to_row(s, project_id) for s in project.scenes])

            # ========== Step 4: videos ==========
            cls._set_progress(project_id, "videos", STEP_PROGRESS["videos"])
            cls._check_stop(project_id)
            logger.info(f"[{project_id}] Step 4: VideoCreator")
            project = vc.generate_scenes(project, output_base, on_scene_done=on_scene_done)
            db.upsert_scenes(project_id, [_scene_to_row(s, project_id) for s in project.scenes])

            # ========== Step 5: compose ==========
            cls._set_progress(project_id, "compose", STEP_PROGRESS["compose"])
            cls._check_stop(project_id)
            logger.info(f"[{project_id}] Step 5: VideoComposer")
            final_path = composer.compose(project, output_base=output_base)
            final_rel = db.relpath_of(final_path)
            db.update_project_final(project_id, final_rel)
            logger.info(f"[{project_id}] 生成完成: {final_rel}")

            cls._set_progress(project_id, "done", STEP_PROGRESS["done"])
            logger.info(f"[{project_id}] 生成完成!")

        except StopGeneration as e:
            logger.warning(f"[{project_id}] {e}")
            try:
                db.update_project_status(project_id, "失败", str(e)[:500])
            except Exception:
                logger.exception(f"[{project_id}] 写停止状态时异常")
            cls._set_progress(project_id, "error", 0, str(e)[:500])

        except Exception as e:
            logger.error(f"[{project_id}] 生成失败: {e}")
            try:
                db.update_project_status(project_id, "失败", str(e)[:500])
            except Exception:
                logger.exception(f"[{project_id}] 写库失败状态时异常")
            cls._set_progress(project_id, "error", 0, str(e)[:500])

        finally:
            cls.release(project_id)

    # ============ 重新合成视频（V2.7：只重跑 compose，不重新生成素材） ============
    @classmethod
    def recompose(cls, project_id: str) -> bool:
        """只重跑 compose 一步：复用现有分镜 video/voice/字幕按原方法重新合成成片。

        与正常生成共享同一把单并发锁（try_start/release）。
        依赖 DB scenes 表已有 image_url/video_url/voice_path 全量齐全。
        返回 True=成功启动后台线程；False=锁被占（有项目在创作中）。
        """
        if not cls.try_start(project_id):
            return False
        cls._set_progress(project_id, "compose", STEP_PROGRESS["compose"])
        thread = threading.Thread(target=cls._recompose_worker, args=(project_id,), daemon=True)
        thread.start()
        return True

    @classmethod
    def _recompose_worker(cls, project_id: str) -> None:
        """后台 worker：DB 重建 Project → compose → 写库。失败保留旧成片文件。"""
        try:
            row = db.get_project(project_id)
            if not row:
                raise RuntimeError(f"项目不存在: {project_id}")

            # ① 校验分镜素材齐全（video 必须有且文件存在）
            db_scenes = db.get_scenes(project_id)
            if not db_scenes:
                raise RuntimeError("项目没有分镜数据，无法重新合成")
            missing = [
                s.get("scene_no")
                for s in db_scenes
                if not s.get("video_url")
                or not (db.PROJECT_ROOT / s["video_url"]).exists()
            ]
            if missing:
                raise RuntimeError(
                    f"以下分镜缺少视频文件，无法重新合成: {missing[:10]}"
                    "（请先完成一次完整生成）"
                )

            # ② DB 行 → Scene 内存对象，重建 Project（config 从快照恢复）
            try:
                snap = json.loads(row.get("config_snapshot") or "{}")
            except json.JSONDecodeError:
                snap = {}
            if not isinstance(snap, dict):
                snap = {}
            video_config = _build_video_config(snap.get("video_config", {}))
            project = Project(
                project_id=project_id,
                name=row.get("name", ""),
                topic=row.get("topic", ""),
                config=video_config,
                scenes=[_db_row_to_scene(s) for s in db_scenes],
            )

            # ③ 状态推进 + compose（路径不变，自动覆盖旧成片；失败时旧文件保留）
            db.update_project_status(project_id, "进行中")
            composer = VideoComposer(ffmpeg_path=get_ffmpeg_path())
            final_path = composer.compose(project, output_base=str(db.OUTPUT_DIR))
            final_rel = db.relpath_of(final_path)
            db.update_project_final(project_id, final_rel)
            logger.info(f"[{project_id}] 重新合成完成: {final_rel}")

            cls._set_progress(project_id, "done", STEP_PROGRESS["done"])

        except StopGeneration as e:
            logger.warning(f"[{project_id}] 重新合成被停止: {e}")
            try:
                db.update_project_status(project_id, "失败", str(e)[:500])
            except Exception:
                logger.exception(f"[{project_id}] 写停止状态时异常")
            cls._set_progress(project_id, "error", 0, str(e)[:500])

        except Exception as e:
            logger.error(f"[{project_id}] 重新合成失败: {e}")
            try:
                db.update_project_status(project_id, "失败", str(e)[:500])
            except Exception:
                logger.exception(f"[{project_id}] 写库失败状态时异常")
            cls._set_progress(project_id, "error", 0, str(e)[:500])

        finally:
            cls.release(project_id)


# 模块级单例（路由层引用）
manager = GenerationManager()
