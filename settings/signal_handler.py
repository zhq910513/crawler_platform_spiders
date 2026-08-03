# -*- coding: utf-8 -*-
# @Time    : 2026-06-25 16:26
# @Description :
# @Link：
"""
全局退出信号控制
"""
import signal
from plugins.log import logger

STOP = False


def handle_exit(sig, frame):
    global STOP
    STOP = True
    logger.warning('收到退出信号，正在安全退出...')


signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)
