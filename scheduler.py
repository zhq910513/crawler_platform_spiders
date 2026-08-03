# -*- coding: utf-8 -*-
# @Time    : 2026-06-25 17:33
# @Description : 常驻消费任务
# @Link：

import time
import threading

from plugins.log import logger

from settings import signal_handler
from openApi.ufl.UFLEplusssInventory import wms_ufl_eplusss_inventory


def start_thread(target, name, args=()):
    """
    启动后台线程。

    :param target: 线程目标函数。
    :param name: 线程名。
    :param args: 目标函数参数。
    :return: 线程对象。
    """
    t = threading.Thread(
        target=target,
        name=name,
        args=args,
        daemon=True
    )
    t.start()
    return t


def task_scheduler():
    """
    启动任务调度器并维护生命周期。

    :return: None。
    """
    threads = []

    # ===== 核心消费者 =====

    threads.append(start_thread(wms_ufl_eplusss_inventory, 'TaskRunner'))

    logger.info("所有工作线程已启动，运行中...")

    try:
        while not signal_handler.STOP:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    for t in threads:
        t.join(timeout=5)

    logger.info("所有工作线程已停止。")


if __name__ == '__main__':
    task_scheduler()
