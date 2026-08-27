"""VoiceActor Agent — 配音生成（V2.0 参数化 / V2.5 本地音色）

调用远程 IndexTTS 服务，将剧本中的旁白/字幕文本转为语音。
支持分镜级配音、情感控制。

V2.5 变更：音色参考音频从在线 URL 改为项目本地文件
（D:\\aivideo_v2\\static\\speaker\\{音色}.mp3，随项目分发），
VoiceStyle.value 即音色文件名（none/afei/awei/aze/nana/lili/wenjun/xiaohua）。

构造函数支持显式传参（GenerationManager 按 config_snapshot 注入 base_url/username/password）；
参数为 None 时从 settings 表读取兜底。ffprobe/ffmpeg 由 services.ffmpeg_utils 动态解析
（优先项目内置 video-platform/bin/，其次系统 PATH，均无则抛错提示配置）。
"""

import logging
import os
import sys
import shutil
import subprocess
import time
from typing import Callable, Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from models.project import Project, Scene, VoiceStyle, TaskStatus
from services.db import get_setting
from services.ffmpeg_utils import get_ffprobe_path

# 项目根目录（voice_actor.py 位于 video-platform/services/ 下）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 音色参考音频本地目录（V2.5：随项目分发，与 /static/speaker 挂载一致）
SPEAKER_DIR = os.path.join(PROJECT_ROOT, "static", "speaker")


def speaker_file(voice_style: VoiceStyle) -> str:
    """音色 → 本地参考音频绝对路径；none/缺失文件给出清晰错误"""
    if voice_style == VoiceStyle.NONE:
        raise RuntimeError("无配音（none）不应进入语音合成，请检查上游跳过逻辑")
    path = os.path.join(SPEAKER_DIR, f"{voice_style.value}.mp3")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"音色参考音频不存在: {path}（请确认 static/speaker/ 已随项目部署）"
        )
    return path


logger = logging.getLogger(__name__)


class VoiceActor:
    """配音 Agent — 调用 IndexTTS 生成语音"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url or get_setting("tts_base_url", "")
        self.username = username or get_setting("tts_username", "")
        self.password = password or get_setting("tts_password", "")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from gradio_client import Client
            self._client = Client(self.base_url, auth=(self.username, self.password))
        return self._client

    def generate_scene_audio(
        self,
        text: str,
        voice_style: VoiceStyle = VoiceStyle.NANA,
        output_path: str = None,
        **kwargs,
    ) -> str:
        """生成单个分镜的配音音频（V2.5：参考音色用本地文件）"""
        ref_audio = speaker_file(voice_style)  # 缺失/无配音 → 清晰报错

        if output_path is None:
            ts = int(time.time())
            output_path = f"scene_voice_{ts}_{voice_style.value}.wav"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

        from gradio_client import handle_file

        logger.info(f"  🎤 TTS [{voice_style.value}]: \"{text[:40]}{'...' if len(text) > 40 else ''}\"")

        result = self.client.predict(
            emo_control_method="与音色参考音频相同",
            prompt=handle_file(ref_audio),
            text=text,
            emo_ref_path=None,
            emo_weight=0.8,
            vec1=kwargs.get("vec1", 0),
            vec2=kwargs.get("vec2", 0),
            vec3=kwargs.get("vec3", 0),
            vec4=kwargs.get("vec4", 0),
            vec5=kwargs.get("vec5", 0),
            vec6=kwargs.get("vec6", 0),
            vec7=kwargs.get("vec7", 0),
            vec8=kwargs.get("vec8", 0),
            emo_text=kwargs.get("emo_text", ""),
            emo_random=kwargs.get("emo_random", False),
            max_text_tokens_per_segment=kwargs.get("max_text_tokens_per_segment", 120),
            param_16=kwargs.get("do_sample", True),
            param_17=kwargs.get("top_p", 0.8),
            param_18=kwargs.get("top_k", 30),
            param_19=kwargs.get("temperature", 0.8),
            param_20=kwargs.get("length_penalty", 0),
            param_21=kwargs.get("num_beams", 3),
            param_22=kwargs.get("repetition_penalty", 10),
            param_23=kwargs.get("max_mel_tokens", 1500),
            api_name="/gen_single",
        )

        server_path = result.get("value", "") if isinstance(result, dict) else str(result)
        if not os.path.exists(server_path):
            raise FileNotFoundError(f"TTS 结果文件未找到: {server_path}")

        shutil.copy2(server_path, output_path)
        size_kb = os.path.getsize(output_path) / 1024
        logger.info(f"  ✅ TTS 完成: {os.path.basename(output_path)} ({size_kb:.1f} KB)")

        return output_path

    def self_test(self, output_path: str = None) -> str:
        """连通性自检：用默认音色（娜娜/女声）合成一句短文本

        成功返回输出文件路径；失败抛异常（连接/鉴权/合成错误均可抛出）。
        供配置页「测试」按钮调用。
        """
        if output_path is None:
            ts = int(time.time())
            output_path = f"tts_test_{ts}.wav"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        return self.generate_scene_audio(
            text="语音合成服务测试",
            voice_style=VoiceStyle.NANA,
            output_path=output_path,
            max_text_tokens_per_segment=50,
        )

    def _get_audio_duration(self, audio_path: str) -> float:
        """使用 ffprobe（动态解析：内置 bin → 系统 PATH）读取音频文件的实际时长（秒）"""
        try:
            cmd = [
                get_ffprobe_path(),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            logger.warning(f"  ⚠️ ffprobe 读取时长失败: {audio_path}")
            return 0.0
        except Exception as e:
            logger.warning(f"  ⚠️ ffprobe 异常: {e}")
            return 0.0

    def generate_project_audio(
        self,
        project: Project,
        output_base: str = "./output",
        on_scene_done: Optional[Callable[[Scene], None]] = None,
    ) -> None:
        """为整个项目生成分镜级配音音频（V2.3：不再合并全片配音）

        V2.3 变更：只保留每个分镜的独立语音文件（scene_{n}.wav），
        不再合成 voiceover.wav 全片配音。逐镜音视频对齐由 VideoComposer 按
        max(视频时长, 语音时长) 完成，故此处无需合并。

        on_scene_done: 可选回调，每完成一个分镜音频后调用（含 voice_path/voice_duration），
            用于分镜级实时写库（前端轮询可见）。
        """
        audio_dir = os.path.join(output_base, project.project_id, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        voice_style = project.config.voice

        scenes_audio_dir = os.path.join(audio_dir, "scenes")
        os.makedirs(scenes_audio_dir, exist_ok=True)

        logger.info(f"\n{'─' * 50}")
        logger.info(f"【配音】VoiceActor — 分镜配音生成 ({voice_style.value})")
        logger.info(f"{'─' * 50}")

        try:
            for scene in project.scenes:
                text = scene.narration or scene.subtitle
                if not text.strip():
                    logger.warning(f"  ⚠️ 分镜 #{scene.scene_id} 无配音文本，跳过")
                    continue

                scene_audio = os.path.join(scenes_audio_dir, f"scene_{scene.scene_id:03d}.wav")
                self.generate_scene_audio(
                    text=text,
                    voice_style=voice_style,
                    output_path=scene_audio,
                )

                voice_duration = self._get_audio_duration(scene_audio)
                if voice_duration > 0:
                    scene.voice_duration = voice_duration
                    logger.info(f"    分镜{scene.scene_id}: 语音时长 {voice_duration:.2f}s")
                else:
                    scene.voice_duration = float(scene.duration)
                    logger.warning(f"  ⚠️ 分镜{scene.scene_id} 语音时长读取失败，使用分镜时长 {scene.duration}s")

                scene.voice_path = scene_audio

                # 分镜级写库回调：单个分镜语音完成后立即写库（回调异常不影响生成流程）
                if on_scene_done:
                    try:
                        on_scene_done(scene)
                    except Exception as e:
                        logger.error(f"  ⚠️ 分镜{scene.scene_id} 写库回调异常: {e}")

            logger.info(f"\n  ✅ 分镜配音全部完成（共 {len(project.scenes)} 个分镜）")

        except Exception as e:
            logger.error(f"❌ 配音生成失败: {e}")
            raise
