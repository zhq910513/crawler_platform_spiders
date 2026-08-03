# -*- coding: utf-8 -*-
# @Time    : 2024/11.html/4 17:55
# @Description :


import importlib.util
import json
from plugins.log import logger
import sys
import os

from datetime import datetime

import vthread as vthread

from databases.sql.sql_for_obj import MysqlProjectDB
from plugins.redis_ctl import RedisCtrl
from sendWarningMsg import FeishuWarningMsg


# logger = logging.getLogger(__name__)


class PublishTask():
    def __init__(self):
        self.db = MysqlProjectDB(database='')
        self.msg = FeishuWarningMsg()
        self.redis_client = RedisCtrl(db=2)
        self.ex_table_name = ['tiktok_video_material','meta_image_material']  # 排除重试的任务

    def search_failed(self):
        '''

        @return:
        '''
        dt = datetime.now().strftime('%Y-%m-%d')
        query_list = self.db.select_to_dict(table_name='scheduler_logs',
                                            where=f'dt="{dt}" and status="failed"')
        for query in query_list:
            target_method_path = query.get('target_method_path')
            count = query.get('count') or 0
            task_table_name = query.get('task_table_name')
            if task_table_name in self.ex_table_name:
                continue
            if count > 5:
                continue
            item = {
                "job_id": query.get('job_id'),
                "job_name": query.get('job_name'),
                "server_group": query.get('server_group'),
                "invoke_target": query.get('invoke_target'),
                "developer": query.get('developer'),
                "task_platform": query.get('task_platform'),
                "target_method_path": target_method_path,
                "cron_expression": query.get('cron_expression'),
                'count': count + 1,
                'task_table_name': task_table_name
            }
            try:
                self.publish(item)
            except Exception as e:
                self.msg.send_warning_msg(f'失败重启运行完成，状态：失败，方法：{target_method_path}，失败原因：{e}')

    def publish(self, item):
        '''
        @param item:
        @return:
        '''
        logger.info(f'开始执行定时任务:{item}')
        server_group = item.get('server_group')
        target_method_path = item.get('target_method_path')
        if not server_group or not target_method_path:
            return
        self.redis_client.rpush(server_group, json.dumps(item))
        logger.info(f'定时任务已发布:{item}')


def publish_task():
    r = PublishTask()
    r.search_failed()


if __name__ == '__main__':
    publish_task()
