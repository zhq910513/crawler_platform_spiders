# -*- coding: utf-8 -*-
# @Time    : 2024/5/17 10:42
# @Description :

from apscheduler.schedulers.blocking import BlockingScheduler
from openApi.ufl.UFLEplusssInventory import wms_ufl_eplusss_inventory

from restart import publish_task

scheduler = BlockingScheduler()
if __name__ == '__main__':
    # 定时，每天1点运行
    scheduler.add_job(wms_ufl_eplusss_inventory, 'interval', minutes=10)  # 亚马逊信用卡扣款状态查询

    try:
        scheduler.start()
    except SystemExit:
        exit()
