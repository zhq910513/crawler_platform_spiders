# -*- coding: utf-8 -*-
# @Time    : 2025/12/10 14:11
# @Description :监控模块
from plugins.log import logger


class TaskMonitor:

    @staticmethod
    def thread_queue_overloaded(queue_size, threshold):
        """
        判断线程池任务队列是否积压
        """
        overloaded = queue_size > threshold

        if overloaded:
            logger.warning(
                f"线程池积压：当前排队任务 {queue_size}，超过阈值 {threshold}"
            )

        return overloaded
