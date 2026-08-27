"""用户主动停止生成标志（独立模块避免 services 间的循环依赖）"""


class StopGeneration(Exception):
    """用户请求停止生成（在客户端长循环中抛出，由 GenerationManager.run 捕获写库 + 退出）"""
    pass