# -*- coding: utf-8 -*-
# @Time    : 2025/12/10 14:11
# @Description :核心调度器

import time
from concurrent.futures import ThreadPoolExecutor

from task_service.config import (
    MAX_WORKERS,
    QUEUE_BLOCK_THRESHOLD,
    IDLE_WAIT_SECONDS
)

from task_service.source_redis import TaskSourceRedis
from task_service.executor import TaskExecutor
from task_service.monitor import TaskMonitor
from plugins.tools import local_ip
from plugins.log import logger


class TaskScheduler:
    """
    任务调度器：负责监听任务源、提交线程池、处理拥堵
    """

    def __init__(self):
        self.redis_key = local_ip()
        self.source = TaskSourceRedis(self.redis_key, db=2)
        self.executor = TaskExecutor()
        self.pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def start(self):
        '''
        核心主循环
        :return:
        '''
        logger.info("任务调度器启动")
        try:
            while True:
                # 检查线程池队列长度 （拥堵保护）
                queue_size = self.pool._work_queue.qsize()
                if queue_size > QUEUE_BLOCK_THRESHOLD:
                    logger.warning(f"线程池积压过多 ({queue_size} > {QUEUE_BLOCK_THRESHOLD})，暂停拉取任务")
                    time.sleep(3)
                    continue  # 队列未空闲，不拉取任务
                task = self.source.get_task()
                if task:
                    try:
                        self.pool.submit(self.executor.execute, task)
                    except RuntimeError as e:
                        logger.error(f"线程池已关闭，无法提交任务: {e}")

                    except Exception as e:
                        logger.error(f"提交任务失败：{e}")
                else:
                    time.sleep(IDLE_WAIT_SECONDS)

        except Exception as e:
            logger.error(f"任务调度器异常: {e}")

        finally:
            logger.error("调度器退出")
            self.cleanup()

    def cleanup(self):
        '''
        资源释放
        :return:
        '''
        try:
            self.pool.shutdown(wait=False)
        except Exception as e:
            logger.error(f"关闭线程池失败: {e}")

        try:
            self.source.close()
        except Exception as e:
            logger.error(f"清理任务源失败: {e}")


if __name__ == "__main__":
    scheduler = TaskScheduler()
    scheduler.start()
