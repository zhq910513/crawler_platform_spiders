# -*- coding: utf-8 -*-
# @Time    : 2025/12/10 14:09
# @Description :

MAX_WORKERS = 30

# 线程池队列积压阈值（超过暂停取任务）
QUEUE_BLOCK_THRESHOLD = int(MAX_WORKERS / 2)

# 空闲时轮询间隔
IDLE_WAIT_SECONDS = 5
