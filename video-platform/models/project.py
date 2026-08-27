"""视频智造平台 - 数据模型"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum
import json
from datetime import datetime


class VideoRatio(str, Enum):
    """视频比例"""
    R16_9 = "16:9"
    R9_16 = "9:16"
    R1_1 = "1:1"


class VideoResolution(str, Enum):
    """
    视频分辨率枚举

    支持横屏（宽>高）和竖屏（高>宽）两种方向，每种分辨率对应 2 个选项：
    - 普清360p: 640×360（横屏）/ 360×640（竖屏）
    - 高清720p: 1280×720（横屏）/ 720×1280（竖屏）
    - 超清1080p: 1920×1080（横屏）/ 1080×1920（竖屏）
    """
    SD_640_LANDSCAPE = "普清360p 横屏"  # 640×360
    SD_640_PORTRAIT = "普清360p 竖屏"    # 360×640
    HD_1280_LANDSCAPE = "高清720p 横屏"  # 1280×720
    HD_1280_PORTRAIT = "高清720p 竖屏"   # 720×1280
    UHD_1920_LANDSCAPE = "超清1080p 横屏"  # 1920×1080
    UHD_1920_PORTRAIT = "超清1080p 竖屏"   # 1080×1920


class VideoStyle(str, Enum):
    """视频风格"""
    REALISTIC = "写实"
    ANIMATION = "动画"
    ANIME = "动漫"
    STYLE_3D = "3D"
    CYBERPUNK = "赛博朋克"
    INK_WASH = "水墨风"
    PIXEL = "像素风"
    OIL_PAINTING = "油画风"


class VoiceStyle(str, Enum):
    """配音音色（V2.5：value=音色文件名，与 static/speaker/*.mp3 一一对应）

    历史值（V2.4 中文风格名）经 from_dict 容错回退为 NONE，无需迁移数据。
    """
    NONE = "none"          # 无配音（前端默认值），跳过语音合成
    AFEI = "afei"          # 阿飞（男声）
    AWEI = "awei"          # 阿伟（男声）
    AZE = "aze"            # 阿哲（男声）
    NANA = "nana"          # 娜娜（女声）
    LILI = "lili"          # 莉莉（女声）
    WENJUN = "wenjun"      # 文君（女声）
    XIAOHUA = "xiaohua"    # 小花（童声）


# 音色中文显示名（前端下拉/详情页展示用，单一来源）
VOICE_LABELS: dict[VoiceStyle, str] = {
    VoiceStyle.NONE: "无配音",
    VoiceStyle.AFEI: "阿飞（男声）",
    VoiceStyle.AWEI: "阿伟（男声）",
    VoiceStyle.AZE: "阿哲（男声）",
    VoiceStyle.NANA: "娜娜（女声）",
    VoiceStyle.LILI: "莉莉（女声）",
    VoiceStyle.WENJUN: "文君（女声）",
    VoiceStyle.XIAOHUA: "小花（童声）",
}


class SceneCamera(str, Enum):
    """镜头语言"""
    EXTREME_LONG = "大远景"
    LONG = "远景"
    MEDIUM = "中景"
    CLOSE_UP = "近景"
    EXTREME_CLOSE_UP = "特写"
    PAN_LEFT = "左移"
    PAN_RIGHT = "右移"
    TILT_UP = "上摇"
    TILT_DOWN = "下摇"
    DOLLY_IN = "推"
    DOLLY_OUT = "拉"


class TaskStatus(str, Enum):
    """任务状态（V2.0 状态枚举，见设计 §9）"""
    PENDING = "等待"
    IN_PROGRESS = "进行中"
    COMPLETED = "完成"
    FAILED = "失败"


@dataclass
class VideoConfig:
    """视频配置"""
    ratio: VideoRatio = VideoRatio.R16_9
    resolution: VideoResolution = VideoResolution.SD_640_LANDSCAPE
    fps: int = 16
    style: VideoStyle = VideoStyle.REALISTIC
    voice: VoiceStyle = VoiceStyle.NONE
    bgm_style: str = "轻音乐"
    target_duration: int = 30  # 秒
    scene_count: int = 5       # 分镜数量


@dataclass
class Scene:
    """单个分镜"""
    scene_id: int
    duration: int                      # 时长（秒，LLM分配，用于控制视频时长）
    description: str                   # 画面描述
    narration: str                     # 配音文本
    subtitle: str                      # 字幕文本
    t2i_prompt: str                    # 文生图提示词（英文）
    i2v_prompt: str                    # 图生视频提示词（英文）
    camera: str                        # 镜头语言

    # 生成后填充
    image_path: Optional[str] = None   # 生成的分镜图片路径
    video_path: Optional[str] = None   # 生成的分镜视频路径
    voice_path: Optional[str] = None   # 生成的分镜语音路径
    voice_duration: Optional[float] = None  # 语音时长（秒，由 ffprobe 读取）
    status: TaskStatus = TaskStatus.PENDING


@dataclass
class Project:
    """视频项目"""
    project_id: str
    name: str
    topic: str
    config: VideoConfig
    scenes: List[Scene] = field(default_factory=list)
    created_at: str = ""
    status: TaskStatus = TaskStatus.PENDING

    # 生成结果
    script_path: Optional[str] = None
    audio_path: Optional[str] = None
    final_video_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        # 重建枚举类型
        config_dict = d.get("config", {})
        # V2.4：voice 可能为 "none"（无配音），容错转换；V2.5：历史中文值回退 NONE
        voice_val = config_dict.get("voice", "none")
        try:
            voice = VoiceStyle(voice_val)
        except ValueError:
            voice = VoiceStyle.NONE
        config = VideoConfig(
            ratio=VideoRatio(config_dict.get("ratio", "16:9")),
            resolution=VideoResolution(config_dict.get("resolution", "普清360p 横屏")),
            fps=config_dict.get("fps", 16),
            style=VideoStyle(config_dict.get("style", "写实")),
            voice=voice,
            bgm_style=config_dict.get("bgm_style", "轻音乐"),
            target_duration=config_dict.get("target_duration", 30),
            scene_count=config_dict.get("scene_count", 5),
        )

        scenes = []
        for s in d.get("scenes", []):
            scenes.append(Scene(
                scene_id=s["scene_id"],
                duration=s["duration"],
                description=s["description"],
                narration=s["narration"],
                subtitle=s["subtitle"],
                t2i_prompt=s["t2i_prompt"],
                i2v_prompt=s["i2v_prompt"],
                camera=s.get("camera", ""),
                image_path=s.get("image_path"),
                video_path=s.get("video_path"),
                voice_path=s.get("voice_path"),
                voice_duration=s.get("voice_duration"),
                status=TaskStatus(s.get("status", "等待")),
            ))

        return cls(
            project_id=d["project_id"],
            name=d["name"],
            topic=d["topic"],
            config=config,
            scenes=scenes,
            created_at=d.get("created_at", ""),
            status=TaskStatus(d.get("status", "等待")),
            script_path=d.get("script_path"),
            audio_path=d.get("audio_path"),
            final_video_path=d.get("final_video_path"),
        )
