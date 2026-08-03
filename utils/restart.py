# -*- coding: utf-8 -*-
# @Time    : 2024/6/24 14:52
# @Description :

import importlib.util
import sys
import os

from datetime import datetime

from databases.sql.sql_for_obj import MysqlProjectDB
from sendWarningMsg import FeishuWarningMsg
from settings.base import BASE_DIR

# 调度日志 ``file_path`` 中与其它机器对齐时使用的项目根目录名（路径片段）。
_PROJECT_ROOT_DIRNAME = ''


def _map_scheduler_file_path_to_local(file_path):
    """
    将调度失败日志里的文件路径映射为当前服务器上的绝对路径。

    他机记录的盘符、前缀可能与当前 ``BASE_DIR`` 不一致；以路径中的
    ``_PROJECT_ROOT_DIRNAME`` 分段为锚，其后相对路径与本机 ``BASE_DIR`` 拼接。
    已属于本机项目树的路径经同样规则处理后结果一致。

    :param file_path: 数据库 ``scheduler_logs.file_path``
    :return: 本机 ``os.path.normpath`` 后的绝对路径； ``file_path`` 为空返回原值；
        路径中不包含项目锚点名时返回规范化后的 ``file_path``。
    """
    if not file_path:
        return file_path
    normalized = os.path.normpath(file_path)
    parts = normalized.split(os.sep)
    anchor_lower = _PROJECT_ROOT_DIRNAME.lower()
    idx = None
    for i, part in enumerate(parts):
        if part.lower() == anchor_lower:
            idx = i
            break
    if idx is None:
        return normalized
    rel_parts = parts[idx + 1:]
    return os.path.normpath(os.path.join(BASE_DIR, *rel_parts))


class RestartFailed():
    def __init__(self):
        self.db = MysqlProjectDB()
        self.msg = FeishuWarningMsg()

    def search_failed(self):
        """
        查询当日失败调度记录并尝试在同机路径下重跑对应函数。

        ``run_fun`` 在主线程顺序执行，避免线程池在主程序退出后继续 ``exec_module``
        时导入标准库 ``concurrent.futures``，触发 ``RuntimeError: can't register
        atexit after shutdown``。

        :return: ``None``
        """
        dt = datetime.now().strftime('%Y-%m-%d')
        # query_list = self.db.select(
        #     table_name='scheduler_logs',
        #     where=(f'dt="{dt}" and status="failed" and '
        #            f'server_ip="{local_ip()}"'),
        # )
        query_list = self.db.select(table_name='scheduler_logs',
                                    where=f'dt="{dt}" and status="failed"')
        for query in query_list:
            path = query.get('file_path')
            name = query.get('func_name')
            if not path or not name:
                continue
            # 日志可能来自其它机器（盘符/前缀不同），统一映射到当前 BASE_DIR 下路径
            path = _map_scheduler_file_path_to_local(path)
            try:
                self.run_fun(path, name)
            except Exception as e:
                self.msg.send_warning_msg(f'失败重启运行完成，状态：失败，文件路径：{path},方法：{name}，失败原因：{e}')

    def run_fun(self, path, name):
        """
        按路径动态导入模块并调用其中的入口函数。

        :param path: 脚本绝对路径，如 ``openApi\\lingxing\\lx_amazon_products.py``
        :param name: 模块内可调用的函数名，如 ``erp_lx_amazon_products``
        :return: ``None``
        """
        # 提取模块名
        module_name = os.path.splitext(os.path.basename(path))[0]
        # 动态导入模块
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        # 获取函数对象
        function_to_call = getattr(module, name)
        function_to_call()


def restart_failed():
    r = RestartFailed()
    r.search_failed()


if __name__ == '__main__':
    r = RestartFailed()
    r.search_failed()
