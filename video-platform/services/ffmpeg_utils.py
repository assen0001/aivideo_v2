"""FFmpeg / FFprobe 路径解析

查找顺序（V2.6）：
    1. 项目内置目录 video-platform/bin/（ffmpeg.exe / ffprobe.exe）
    2. 系统 PATH 环境变量（shutil.which）
    3. 均未找到 → 抛 FileNotFoundError，提示用户下载并放入 bin 目录或加入 PATH

用法（推荐使用 get_* 函数，支持动态解析与友好报错）：
    from services.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path
    ffmpeg = get_ffmpeg_path()
"""

import os
import shutil

# 项目内置二进制目录：video-platform/bin/
_BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")

# 兼容旧引用（V2.0 常量入口，纯路径拼接、不校验存在性；新代码请使用 get_* 函数）
FFMPEG_PATH = os.path.join(_BIN_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(_BIN_DIR, "ffprobe.exe")


def _resolve(bin_file: str, exe_name: str) -> str:
    """按「内置 bin → 系统 PATH」顺序查找可执行文件；均无则抛出带配置指引的错误。"""
    for candidate in (bin_file, exe_name):
        path = os.path.join(_BIN_DIR, candidate)
        if os.path.isfile(path):
            return path
    which = shutil.which(exe_name)
    if which:
        return which
    raise FileNotFoundError(
        f"未找到 {exe_name}！请下载 FFmpeg（https://ffmpeg.org/download.html）"
        f"并将 {exe_name} 放入项目 video-platform/bin/ 目录，"
        f"或将 FFmpeg 所在目录加入系统 PATH 后重启服务。"
    )


def get_ffmpeg_path() -> str:
    """解析 FFmpeg 可执行文件路径：优先项目内置 bin，其次系统 PATH；均无则报错。"""
    return _resolve("ffmpeg.exe", "ffmpeg")


def get_ffprobe_path() -> str:
    """解析 FFprobe 可执行文件路径：优先项目内置 bin，其次系统 PATH；均无则报错。"""
    return _resolve("ffprobe.exe", "ffprobe")
