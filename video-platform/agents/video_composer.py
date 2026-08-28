"""VideoComposer Agent — 最终视频合成（V2.6 FFmpeg 动态解析）

将分镜视频、配音、背景音乐、字幕合成为完整视频。
FFmpeg 路径由 services.ffmpeg_utils.get_ffmpeg_path() 动态解析：
优先项目内置 video-platform/bin/，其次系统 PATH，均无则抛错提示配置。
"""

import logging
import os
import subprocess
import sys
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from models.project import (
    Project, Scene, TaskStatus, VideoRatio, VideoResolution,
)
from services.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

# ============ 字幕字体（V2.7：内置字体，兼容 Linux / Windows 部署） ============
# OTF 字体文件本身跨平台，但 ffmpeg 加载机制不同：
#   - Linux/macOS：libass 走 fontconfig provider，认 subtitles 滤镜的 fontsdir 参数。
#     → 用项目内置思源黑体（Apache 2.0 可商用），随仓库分发在 video-platform/assets/fonts/，
#       fontsdir 指向该目录，杜绝服务器缺中文字体导致字幕豆腐块。
#   - Windows：libass 走 directwrite provider，**忽略 fontsdir**，直接查系统字体库。
#     → 无需任何字体文件，Fontname 直接用系统自带的微软雅黑（Win7+ 全自带）即可。
FONTS_DIR = os.path.join(_root, "assets", "fonts")
_FONT_FILE = os.path.join(FONTS_DIR, "SourceHanSansSC-Regular.otf")

if sys.platform.startswith("win"):
    # Windows：系统字体兜底，fontsdir 无效不传
    SUBTITLE_FONT_NAME = "Microsoft YaHei"
    SUBTITLE_FONTSDIR = None
else:
    # Linux/macOS：强制项目内置思源黑体
    SUBTITLE_FONT_NAME = "Source Han Sans SC"
    SUBTITLE_FONTSDIR = FONTS_DIR

# ffmpeg 滤镜参数转义：Windows 盘符冒号 / 分隔符冒号需转义；路径统一用正斜杠。
def _escape_filter_arg(p: str) -> str:
    return p.replace("\\", "/").replace(":", "\\:").replace(",", "\\,")

# 分辨率映射（与 video_creator.py 同步）
RESOLUTION_MAP = {
    (VideoRatio.R16_9, VideoResolution.SD_640_LANDSCAPE): (640, 360),
    (VideoRatio.R16_9, VideoResolution.HD_1280_LANDSCAPE): (1280, 720),
    (VideoRatio.R16_9, VideoResolution.UHD_1920_LANDSCAPE): (1920, 1080),
    (VideoRatio.R9_16, VideoResolution.SD_640_PORTRAIT): (360, 640),
    (VideoRatio.R9_16, VideoResolution.HD_1280_PORTRAIT): (720, 1280),
    (VideoRatio.R9_16, VideoResolution.UHD_1920_PORTRAIT): (1080, 1920),
    (VideoRatio.R1_1, VideoResolution.SD_640_LANDSCAPE): (512, 512),
    (VideoRatio.R1_1, VideoResolution.HD_1280_LANDSCAPE): (768, 768),
    (VideoRatio.R1_1, VideoResolution.UHD_1920_LANDSCAPE): (1024, 1024),
}

# ============ 字幕参数（V2.4 新增，可直接修改） ============
# 字幕最多显示行数（超长截断 + 省略号）
SUBTITLE_MAX_LINES = 2
# 各画面比例下每行最多中文字符数 —— 调这里即可控制字幕宽度
# 16:9 → 30字/行，9:16 → 14字/行，1:1 → 18字/行
SUBTITLE_MAX_CHARS_BY_RATIO = {
    VideoRatio.R16_9: 30,
    VideoRatio.R9_16: 14,
    VideoRatio.R1_1: 18,
}


class VideoComposer:
    """视频合成 Agent — FFmpeg"""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """ffmpeg_path 为空时自动解析：项目内置 bin → 系统 PATH；均无则抛错提示配置"""
        self.ffmpeg = ffmpeg_path or get_ffmpeg_path()

    def compose(
        self,
        project: Project,
        audio_path: Optional[str] = None,
        bgm_path: Optional[str] = None,
        output_base: str = "./output",
    ) -> str:
        """合成最终视频（V2.3：逐镜音视频对齐）

        V2.3 变更：不再使用全片配音（voiceover.wav 已废弃）。
        每个分镜画面时长 = max(分镜视频真实时长, 分镜语音时长)：
        - 语音短 → 画面保留 + 语音补静音
        - 视频短 → 画面减速（setpts）延长到语音时长
        每镜对齐后已内嵌语音轨，直接 concat + 字幕烧录输出。
        audio_path / bgm_path 参数保留仅为兼容旧调用，V2.3 起不再参与混音。
        """
        final_dir = os.path.join(output_base, project.project_id, "final")
        os.makedirs(final_dir, exist_ok=True)

        scenes = [
            s for s in project.scenes
            if s.video_path and os.path.exists(s.video_path)
        ]
        scenes.sort(key=lambda s: s.scene_id)

        logger.info(f"  项目总分镜数: {len(project.scenes)}")
        logger.info(f"  有效分镜视频数: {len(scenes)}")

        if not scenes:
            raise RuntimeError("没有可合成的分镜视频")

        temp_dir = os.path.join(final_dir, "_temp")
        os.makedirs(temp_dir, exist_ok=True)

        output_path = os.path.join(final_dir, f"{project.project_id}.mp4")

        try:
            aligned_scenes = []
            scene_durations = []  # 每镜对齐后的最终画面时长（字幕/拼接用）
            for i, scene in enumerate(scenes):
                voice_path = scene.voice_path
                voice_dur = scene.voice_duration or 0

                if voice_path and os.path.exists(voice_path) and voice_dur > 0:
                    aligned, final_dur = self._align_audio_video(
                        scene.video_path, voice_path, voice_dur, temp_dir, i
                    )
                    aligned_scenes.append(aligned)
                    scene_durations.append(final_dur)
                    logger.info(
                        f"    分镜{scene.scene_id}: 视频={final_dur:.2f}s "
                        f"(语音{voice_dur:.2f}s {'减速' if voice_dur >= final_dur - 0.05 else '补静音'})"
                    )
                else:
                    logger.warning(f"  ⚠️ 分镜{scene.scene_id} 无语音文件，使用原视频（无声）")
                    video_dur = self._probe_duration(scene.video_path) or scene.duration
                    aligned_scenes.append(scene.video_path)
                    scene_durations.append(video_dur)

            logger.info(f"  Step 1 ✅ 音视频对齐完成")

            concat_video = self._concat_videos(aligned_scenes, temp_dir)
            logger.info(f"  Step 2 ✅ 分镜拼接: {concat_video}")

            if bgm_path and os.path.exists(bgm_path):
                logger.warning("  ⚠️ V2.3 起 bgm 混音未启用（分镜语音已内嵌音轨），忽略 bgm 参数")

            width, height = RESOLUTION_MAP.get(
                (project.config.ratio, project.config.resolution),
                (640, 360),
            )
            max_chars = SUBTITLE_MAX_CHARS_BY_RATIO.get(project.config.ratio, 18)
            subtitle_text = self._build_subtitle_text(
                scenes, scene_durations, width, height, max_chars
            )
            self._final_render(
                os.path.abspath(concat_video),
                None,  # V2.3: 不再混合全片配音（每镜已内嵌）
                os.path.abspath(output_path),
                subtitle_text, temp_dir,
            )
            logger.info(f"  Step 4 ✅ 最终合成: {output_path}")

            self._cleanup(temp_dir)

            project.final_video_path = output_path
            project.status = TaskStatus.COMPLETED

            return output_path

        except Exception as e:
            project.status = TaskStatus.FAILED
            logger.error(f"❌ 视频合成失败: {e}")
            raise

    def _concat_videos(self, video_paths: list, temp_dir: str) -> str:
        """用 concat demuxer 拼接视频"""
        filelist = os.path.join(temp_dir, "filelist.txt")
        with open(filelist, "w", encoding="utf-8") as f:
            for path in video_paths:
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        output = os.path.join(temp_dir, "concat_temp.mp4")
        cmd = [
            self.ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", filelist,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "96k",
            "-y",
            output,
        ]
        self._run_ffmpeg(cmd)
        return output

    def _probe_duration(self, media_path: str) -> float:
        """ffprobe 读取媒体文件实际时长（秒）；失败返回 0.0"""
        try:
            cmd = [
                get_ffprobe_path(), "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                media_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"  ⚠️ ffprobe 读取时长失败 {media_path}: {e}")
        return 0.0

    def _align_audio_video(self, video_path: str, voice_path: str,
                           voice_dur: float, temp_dir: str, scene_index: int):
        """逐镜音视频对齐（V2.3）：画面时长 = max(视频真实时长, 语音时长)。

        - 语音短于视频：画面不变速，语音 `apad` 补静音到画面时长
        - 语音长于视频：画面 `setpts` 减速延长到语音时长（保留完整配音）
        返回 (对齐后文件路径, 最终画面时长)
        """
        output = os.path.join(temp_dir, f"scene_aligned_{scene_index:03d}.mp4")

        video_dur = self._probe_duration(video_path)
        if video_dur <= 0:
            video_dur = 5.0  # ffprobe 失败兜底
        final_dur = max(video_dur, voice_dur)
        if final_dur <= 0:
            final_dur = 5.0

        if voice_dur < video_dur:
            # 语音短：画面保留，语音补静音（apad 无限补 + -t 截断到画面时长）
            filter_complex = "[1:a]apad[a]"
            map_args = ["-map", "0:v", "-map", "[a]"]
        else:
            # 视频短：画面减速延长到语音时长（setpts=PTS×ratio）
            ratio = final_dur / max(video_dur, 0.001)
            filter_complex = (
                f"[0:v]setpts=PTS*{ratio:.6f}[v];"
                f"[1:a]aresample=async=1[a]"
            )
            map_args = ["-map", "[v]", "-map", "[a]"]

        cmd = [
            self.ffmpeg,
            "-i", video_path,
            "-i", voice_path,
            "-filter_complex", filter_complex,
            *map_args,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", f"{final_dur:.3f}",
            "-y",
            output,
        ]
        self._run_ffmpeg(cmd)
        return output, final_dur

    def _final_render(self, video_path: str, audio_path: Optional[str],
                      output_path: str, subtitle_text: Optional[str] = None,
                      temp_dir: Optional[str] = None):
        """最终合成：拼接视频（自带逐镜音轨） + 字幕内嵌（V2.3：不再混合外部音轨）

        V2.7：字幕字体平台自适应 —— Linux/macOS 用 fontsdir 强制项目内置思源黑体，
        Windows 用系统微软雅黑（directwrite 忽略 fontsdir，直接查系统字体）。
        """
        cmd = [self.ffmpeg, "-i", video_path]

        ass_path = None
        ffmpeg_cwd = None
        if subtitle_text:
            if temp_dir:
                ass_path = os.path.join(temp_dir, "subtitles.ass")
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(subtitle_text)
                vf = "subtitles=subtitles.ass"
                if SUBTITLE_FONTSDIR:
                    # fontsdir 用相对路径（相对 ffmpeg 的 cwd=temp_dir）：
                    # 绝对路径含盘符冒号（D:\:）会被 ffmpeg filter 解析吃掉，Windows 必炸。
                    fonts_rel = os.path.relpath(SUBTITLE_FONTSDIR, temp_dir).replace(os.sep, "/")
                    vf += f":fontsdir={fonts_rel}"
                cmd.extend(["-vf", vf])
                ffmpeg_cwd = temp_dir
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".ass", mode="w", delete=False, encoding="utf-8") as f:
                    f.write(subtitle_text)
                    ass_path = f.name
                vf = f"subtitles='{ass_path}'"
                if SUBTITLE_FONTSDIR:
                    vf += f":fontsdir={_escape_filter_arg(SUBTITLE_FONTSDIR)}"
                cmd.extend(["-vf", vf])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-y",
            output_path,
        ])

        self._run_ffmpeg(cmd, cwd=ffmpeg_cwd)

        if ass_path and not temp_dir:
            try:
                os.unlink(ass_path)
            except Exception:
                pass

    def _build_subtitle_text(self, scenes: list, durations: list,
                             width: int, height: int, max_chars: int) -> str:
        """构建 ASS 字幕内容字符串（V2.4：智能换行 + 字号按画面宽度自适应）

        字号 = 画面宽 / 每行字符数 × 0.95（留 5% 边距），保证 max_chars 个字
        刚好放得下 → 用户改 SUBTITLE_MAX_CHARS_BY_RATIO 时字号自动跟随，
        不会出现"改了字数仍溢出"的情况。
        """
        if not scenes:
            return ""

        font_size = max(16, round(width / max_chars * 0.95))

        current_sec = 0.0
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, "
            "SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            f"Style: Default,{SUBTITLE_FONT_NAME},{font_size},&H00FFFFFF,&H000000FF,"
            "&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,"
            "10,10,30,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, "
            "MarginR, MarginV, Effect, Text",
        ]

        for idx, s in enumerate(scenes):
            dur = durations[idx] if idx < len(durations) and durations[idx] > 0 else s.duration
            start_ts = self._sec_to_ass_time(current_sec)
            end_ts = self._sec_to_ass_time(current_sec + dur)
            text = s.subtitle.replace("{", "\\{").replace("}", "\\}")
            text = self._wrap_subtitle(text, max_chars, SUBTITLE_MAX_LINES)
            lines.append(
                f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}"
            )
            current_sec += dur

        return "\n".join(lines)

    def _wrap_subtitle(self, text: str, max_chars: int, max_lines: int = 2) -> str:
        """字幕智能换行（V2.4）

        - 优先在中文/英文标点（、，。！？；：,.!?;: 空格）处断行，视觉最自然
        - 累计字符数达到 max_chars 时强制断行（无标点长串兜底）
        - 超过 max_lines 行时截断，末行去尾标点补省略号
        行间用 ASS 换行符 \\N 连接。
        """
        if not text or max_lines <= 1:
            return text

        # 1. 按标点切成语义段（标点保留在段尾，作为天然换行点）
        segments, cur = [], ""
        for ch in text:
            cur += ch
            if ch in "、，。！？；：,.!?;: ":
                segments.append(cur)
                cur = ""
        if cur:
            segments.append(cur)

        # 2. 贪心组行：段累加不超 max_chars 就同行，否则开新行
        lines, cur_line = [], ""
        for seg in segments:
            if len(cur_line) + len(seg) <= max_chars:
                cur_line += seg
                continue
            if cur_line:
                lines.append(cur_line)
                cur_line = ""
            # 单段超长（连续无标点）：按 max_chars 硬切
            while len(seg) > max_chars:
                lines.append(seg[:max_chars])
                seg = seg[max_chars:]
            cur_line = seg
        if cur_line:
            lines.append(cur_line)

        # 3. 超行数截断 + 省略号
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip("、，。！？；：,.!?;: ") + "…"

        return "\\N".join(lines)

    def _sec_to_ass_time(self, sec: float) -> str:
        """将秒转换为 ASS 时间格式 H:MM:SS.cc"""
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int((sec - int(sec)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _run_ffmpeg(self, cmd: list, cwd: Optional[str] = None):
        """执行 FFmpeg 命令"""
        logger.debug(f"FFmpeg: {' '.join(cmd)} (cwd={cwd})")
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=cwd,
        )
        if process.returncode != 0:
            error = process.stderr[-500:] if process.stderr else "unknown"
            raise RuntimeError(f"FFmpeg 失败 (code={process.returncode}): {error}")

    def _cleanup(self, temp_dir: str):
        """清理临时文件"""
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
