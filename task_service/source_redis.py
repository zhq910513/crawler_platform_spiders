# -*- coding: utf-8 -*-
# @Time    : 2025/12/10 14:09
# @Description :任务来源：Redis,MQ等，视情况而定


import time
from plugins.redis_ctl import RedisCtrl

from plugins.log import logger


class TaskSourceRedis(object):
    """
    Redis 任务源：负责从 Redis 拉取任务
    """

    def __init__(self, redis_key,db=2):
        self.redis = RedisCtrl(db=db)
        self.redis_key = redis_key

    def get_task(self):
        """
        从 Redis 拉取任务
        """
        try:
            raw = self.redis.rpop(self.redis_key)
            if raw:
                return raw.decode()
            return None

        except UnicodeDecodeError:
            logger.error("任务解码失败")

        except Exception as e:
            logger.error(f"Redis 获取任务失败：{e}")
            time.sleep(5)

        return None

    def close(self):
        """关闭连接"""
        try:
            self.redis.close()
        except Exception as e:
            logger.error(f"关闭 Redis 失败: {e}")
