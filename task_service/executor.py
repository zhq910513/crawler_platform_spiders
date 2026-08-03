# -*- coding: utf-8 -*-
# @Time    : 2025/12/10 14:10
# @Description :任务执行器,执行任务的逻辑

import contextlib
import importlib
from datetime import datetime, timedelta
import json

import requests
from concurrent.futures import ThreadPoolExecutor

from plugins.feishu_monitor import feishu_monitor_success, feishu_monitor_failed, feishu_monitor_data_cnt, \
    feishu_monitor_timeout
from plugins.redis_ctl import RedisCtrl
from plugins.tools import local_ip
from sendWarningMsg import FeishuWarningMsg
from settings import PY_ENV
from settings.base import MANAGER_HOST
from databases.sql.mysqldb import MysqlProjectDB
# 配置日志记录
from plugins.log import logger


class TaskExecutor(object):
    def __init__(self, max_workers=30):
        self.redis_client = RedisCtrl(db=2)
        self.module_cache = {}  # 模块缓存

        self.local_ip = local_ip()
        self.db = MysqlProjectDB()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    @staticmethod
    def validate_task_path(task_path):
        '''
        验证任务路径格式是否正确。
        @param task_path:
        @return:
        '''
        if '.' not in task_path:
            raise ValueError("任务路径格式不正确，必须包含至少一个 '.'")
        return task_path

    def import_module(self, module_path):
        # if module_path in self.module_cache:
        #     return self.module_cache[module_path]
        try:
            module = importlib.import_module(module_path)
            # self.module_cache[module_path] = module
            return module
        except Exception as e:
            logger.error(f"导入模块失败: {module_path}, 错误: {e}")

    @staticmethod
    def get_function(module, func_name):
        try:
            func = getattr(module, func_name)
            if not callable(func):
                raise AttributeError(f"模块 {module.__name__} 中的 {func_name} 不是可调用对象")
            return func
        except Exception as e:
            logger.error(f"获取函数失败: {func_name}, 错误: {e}")

    def execute(self, task_args):
        data = json.loads(task_args)
        _task_path = data.get('target_method_path')
        platform = data.get('task_platform')
        job_id = data.get('job_id')
        task_path = self.validate_task_path(_task_path)
        module_path, func_name = task_path.rsplit('.', 1)
        try:
            module = self.import_module(module_path)
            if not module:
                return
            func = self.get_function(module, func_name)
            func_path = f"{func.__module__}.{func_name}"
            job_name = data.get('job_name')
            developer = data.get('developer')
            task_table_name = data.get('task_table_name')
            try:
                db = MysqlProjectDB(database='overseas_crawler_admin')
            except Exception as e:
                feishu_monitor_failed.send_warning_msg(f"【{self.local_ip}】 链接数据库失败,启动文件：{func_name}",
                                                       users=['haijun'])
                self.monitor_callback(status=4, job_id=job_id, message=f'{job_name}=>初始化数据库失败')
                logger.error(f"初始化数据库失败: {task_path}, 错误: {e}")
                return
            _start_time = datetime.now()
            start_time = _start_time.strftime('%Y-%m-%d %H:%M:%S')
            try:
                self.monitor_callback(status=2, job_id=job_id, message=f'{job_name}=>开始任务')
                func()
                _end_time = datetime.now()
                end_time = _end_time.strftime('%Y-%m-%d %H:%M:%S')
                self.save_log(db, data, 'success', start_date=_start_time, is_send_timeout_msg=True)
                success_msg = (f'运行成功：\n'
                               f'服务器：{self.local_ip} \n'
                               f'平台：{platform} \n'
                               f'任务名：{job_name}\n'
                               f'函数路径：{func_path}\n'
                               f'表名：{task_table_name}\n'
                               f'开始时间：{start_time}\n'
                               f'结束时间：{end_time}')
                feishu_monitor_success.send_warning_msg(success_msg)
                if task_table_name:
                    table_name_split = task_table_name.split(',')
                    with contextlib.suppress(Exception):
                        for table_name in table_name_split:
                            self.monitor_table_data_count(table_name=table_name)

                self.monitor_callback(status=3, job_id=job_id, message=f'{job_name}=>结束任务')
            except Exception as e:
                end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                error_msg = (f'运行失败：\n'
                             f'服务器：{self.local_ip} \n'
                             f'平台：{platform} \n'
                             f'任务名：{job_name}\n'
                             f'函数路径：{func_path} \n'
                             f'表名：{task_table_name}\n'
                             f'开始时间：{start_time}\n'
                             f'结束时间：{end_time}\n'
                             f'原因：{e}')
                feishu_monitor_failed.send_warning_msg(f"{error_msg}", users=[developer])
                self.save_log(db, data, 'failed', start_date=_start_time, is_send_timeout_msg=False)
                self.monitor_callback(status=4, job_id=job_id, message=f'{job_name}=>任务失败')

        except Exception as e:
            logger.error(f"执行任务失败: {task_path}, 错误: {e}")

    def save_log(self, db, data: dict, status, start_date=None, is_send_timeout_msg=False):
        '''
        {
            "job_id": 354,
            "job_name": "meta动态素材创意数据",
            "server_group": "172.29.33.173",
            "invoke_target": "module_task.scheduler_job.job",
            "developer": "haijun",
            "task_platform": "Meta",
            "target_method_path": "openApi.meta.dc_creative.meta_dc_creative_data",
            "cron_expression": "0 0 1 * * ?"
        }
        @param db:
        @param data:
        @param status:
        @param start_date:任务执行的开始时间
        @param is_send_timeout_msg: 是否发送超时消息（失败任务不用发）
        @return:
        '''

        log_table = 'scheduler_logs'
        target_method_path = data.get('target_method_path')
        task_table_name = data.get('task_table_name')
        date_now = datetime.now()
        dt = date_now.strftime('%Y-%m-%d')
        data['dt'] = dt
        data['status'] = status
        data['expected_start_date'] = start_date.strftime('%Y-%m-%d %H:%M:%S')
        query = db.select_by_sql(
            f'select expected_start_date from {log_table} where dt="{dt}" and target_method_path="{target_method_path}" and status="failed"')
        if not query:
            # 可能存在每天多次执行的任务，如果不存在失败任务，表明是当天第一次执行或者下一次执行（也会存在一直失败的问题）
            # 对于成功的下次执行任务和未执行的任务，开始时间就是任务开始执行的时间
            _expected_start_date = start_date
            db.add_replace('scheduler_logs', **data)
        else:
            db.update(table_name=log_table, where=f'dt="{dt}" and target_method_path="{target_method_path}"', **{
                'status': status
            })
            # 对于失败任务，开始时间是第一次执行的时间
            _expected_start_date = query[0].get('expected_start_date')
        if not is_send_timeout_msg:
            # 失败任务不需要发送是否超时的提醒
            return
        if isinstance(_expected_start_date, datetime) and (date_now - _expected_start_date).total_seconds() > 3600:
            feishu_monitor_timeout.send_warning_msg(
                f"运行超时：\n"
                f"表名：【{task_table_name}】\n"
                f"函数路径：【{target_method_path}】\n"
                f"预计开始时间：{_expected_start_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"结束时间：{date_now.strftime('%Y-%m-%d %H:%M:%S')}",
                users=['xiaoxiang', 'haijun']
            )
        return

    def monitor_callback(self, status, job_id, message=None):
        '''
        监控回调
        '''
        url = F'{MANAGER_HOST}/api/open_api/job/changeTargetStatus'
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            "jobId": job_id,
            "targetStatus": status
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(data))
            resp_dict = response.json()
            logger.info(f"{message},data:{data},监控回调结果：{resp_dict}")
        except Exception as e:
            logger.error(f'调用接口失败，{e},data={data}')

    def monitor_table_data_count(self, table_name):
        '''
        监控表数据数量
        :param table_name:
        :return:
        '''
        today = datetime.now()
        start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        if 'fs_' not in table_name:
            rest = self.query_with_dt(table_name, start_date, end_date)
            if not rest:
                rest = self.query_with_insert_time(table_name)
        else:
            rest = self.query_with_insert_time(table_name)
        feishu_monitor_data_cnt.send_warning_msg(rest)

    def query_with_dt(self, table_name, start_date, end_date):
        sql = f"""
               SELECT
                 count(dt),dt
               FROM
                 {table_name}
               WHERE
                 dt BETWEEN "{start_date}" AND "{end_date}"
                GROUP BY dt
           """
        try:
            query_set = self.db.select_by_sql(sql)
        except Exception as e:
            return
        if not query_set:
            return
        item_list = [f'数据表:{table_name}']
        for query in query_set:
            item_list.append(f'日期：{query.get("dt")}，总数据量：{query.get("count(dt)")}')
        return '\n'.join(item_list)

    def query_with_insert_time(self, table_name):
        today = datetime.now()
        start_date = (today - timedelta(days=0)).strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        sql = f"""
           SELECT
             count(insert_time) as cnt,date(insert_time) as dt
           FROM
             {table_name}
           WHERE
             insert_time BETWEEN "{start_date}" AND "{end_date}"
            GROUP BY DATE(insert_time)
        """
        query_set = self.db.select_by_sql(sql)
        if query_set:
            item_list = [f'数据表:{table_name}']
            for query in query_set:
                item_list.append(f'日期：{query.get("dt")}，插入总数据量：{query.get("cnt")}')
            return '\n'.join(item_list)
