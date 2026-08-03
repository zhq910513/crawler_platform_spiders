# -*- coding: utf-8 -*-
# @Time    : 2025/3/26 11:45
# @Description :

import time
import contextlib
import decimal
import json
import re
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict
import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor
from retry import retry
from six import itervalues

from plugins.log import logger
from plugins.redis_ctl import RedisCtrl
from settings.base import *


class MysqlProjectDB:
    placeholder = "%s"
    maxlimit = -1

    def __init__(self, host=MYSQL_HOST, port=MYSQL_PORT, database=MYSQL_DB,
                 user=MYSQL_USER, passwd=MYSQL_PWD, pool_size: int = 10):
        """
        初始化数据库连接池
        :param db_config: MySQL 连接配置
        :param pool_size: 连接池最大连接数
        """
        self.pool = PooledDB(
            maxusage=None,
            creator=pymysql,
            mincached=2,  # 最小空闲连接数
            maxcached=pool_size,  # 最大空闲连接数
            maxconnections=pool_size,  # 最大连接数
            blocking=True,  # 连接池满时是否等待
            host=host,
            user=user,
            password=passwd,
            database=database,
            port=port,
            charset='utf8mb4',
        )
        self.redis = RedisCtrl()

    @staticmethod
    def escape(string):
        return '`%s`' % string

    def get_mysql_type(self, value):
        """
        根据传入的值自动识别 MySQL 数据类型。

        :param value: 字段的值
        :return: 对应的 MySQL 数据类型
        """

        def _get_datetime_type(value):
            """
            检查字符串是否符合日期或日期时间格式
            @param value:
            @return:
            """
            date_formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]
            for date_format in date_formats:
                try:
                    datetime.strptime(value, date_format)
                    return 'DATE' if date_format == "%Y-%m-%d" else 'DATETIME'
                except ValueError:
                    continue
            return None

        # 类型映射字典
        type_mapping = {
            int: 'INT',
            float: 'FLOAT',
            bool: 'BOOLEAN',
            bytes: 'LONGBLOB',
            bytearray: 'LONGBLOB',
            dict: 'JSON',
            list: 'JSON',
            # type(None): 'NULL',  # None 类型直接对应 NULL
            decimal.Decimal: 'DECIMAL(20, 10)',
            datetime: 'DATETIME'
        }

        # 检查基础类型
        if isinstance(value, tuple(type_mapping.keys())):
            return type_mapping[type(value)]

        # 处理字符串类型（日期、时间、常规字符串）
        if isinstance(value, str):
            datetime_type = _get_datetime_type(value)
            if datetime_type:
                return datetime_type
            return 'VARCHAR(255)' if len(value) <= 255 else 'TEXT'
        if value is None:
            return 'VARCHAR(255)'
        # 如果无法识别类型，抛出异常
        raise TypeError(f"不支持的值类型: {type(value)}")

    def create_table_by_dict(self, table_name: str, data_dict: Dict[str, Any], table_comment: str):
        """
        根据数据字典自动创建 MySQL 数据表。

        :param table_name: 要创建的表名
        :param data_dict: 字段名和字段值组成的字典，字段值决定字段的数据类型
        :param table_comment: 表的备注
        """
        # 获取数据类型
        columns = ["`insert_time` DATETIME"]
        for field, value in data_dict.items():
            mysql_type = self.get_mysql_type(value)
            columns.append(f"`{field}` {mysql_type}")
        # 拼接表创建语句
        columns_sql = ",\n    ".join(columns)
        comment_sql = f"COMMENT = '{table_comment}'" if table_comment else ""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            {columns_sql}
        ) {comment_sql};
        """
        # 执行 SQL 语句创建表
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(create_table_sql)
            print(f"表 `{table_name}` 创建成功！")
        except Exception as e:
            print(f"创建表 `{table_name}` 时发生错误: {e}")

    def select(self, table_name: str, what: str = "*", where: str = '', offset: int = 0, limit: int = None,
               join=None):
        """查询数据"""
        # table_name = self.escape(table_name)
        if isinstance(what, list) or isinstance(what, tuple) or what is None:
            what = ','.join(self.escape(f) for f in what) if what else '*'
        sql_query = "SELECT %s FROM %s" % (what, table_name)
        if join:
            sql_query += " %s" % join
        if where:
            sql_query += " WHERE %s" % where
        if limit:
            sql_query += " LIMIT %d, %d" % (offset, limit)
        elif offset:
            sql_query += " LIMIT %d, %d" % (offset, self.maxlimit)

        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                rest = cursor.fetchall()
                return rest if rest else []
        except pymysql.MySQLError as e:
            logger.error(f"查询失败: {e}")
            return []
        finally:
            connection.close()

    def select_to_dict(self, table_name: str = None, what: str = "*", where: str = "",
                       order: str = None, offset: int = 0, limit: int = None) -> dict:
        '''
        查询的数据集转为dict
        @param table_name:
        @param what:
        @param where:
        @param order:
        @param offset:
        @param limit:
        @return:
        '''
        table_name = self.escape(table_name)
        if isinstance(what, list) or isinstance(what, tuple) or what is None:
            what = ','.join(self.escape(f) for f in what) if what else '*'
        sql_query = "SELECT %s FROM %s" % (what, table_name)
        if where:
            sql_query += " WHERE %s" % where
        if order:
            sql_query += ' ORDER BY %s' % order
        if limit:
            sql_query += " LIMIT %d, %d" % (offset, limit)
        elif offset:
            sql_query += " LIMIT %d, %d" % (offset, self.maxlimit)
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                for row in cursor:
                    yield row
        except pymysql.MySQLError as e:
            logger.error(f"查询失败: {e}")
            return []
        finally:
            connection.close()

    def replace(self, table_name, **values):
        '''
        替换
        @param table_name:
        @param values: dict
        @return:
        '''
        table_name = self.escape(table_name)
        if values:
            _keys = ", ".join(self.escape(k) for k in values)
            _values = ", ".join([self.placeholder, ] * len(values))
            sql_query = "REPLACE INTO %s (%s) VALUES (%s)" % (table_name, _keys, _values)
        else:
            sql_query = "REPLACE INTO %s DEFAULT VALUES" % table_name

        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                if values:
                    cursor.execute(sql_query, list(itervalues(values)))
                else:
                    cursor.execute(sql_query)
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f"查询失败: {e}")
            return []
        finally:
            connection.close()

    def insert(self, table_name, **values):
        '''
        插入
        @param table_name:
        @param values: dict
        @return:
        '''
        table_name = self.escape(table_name)
        if values:
            values.update({
                'insert_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
            _keys = ", ".join((self.escape(k) for k in values))
            _values = ", ".join([self.placeholder, ] * len(values))
            sql_query = "INSERT INTO %s (%s) VALUES (%s)" % (table_name, _keys, _values)
        else:
            sql_query = "INSERT INTO %s DEFAULT VALUES" % table_name

        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                if values:
                    cursor.execute(sql_query, list(itervalues(values)))
                else:
                    cursor.execute(sql_query)
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f"插入数据失败:{values}, {e}")
            return []
        finally:
            connection.close()

    def update(self, table_name, where="1=0", **values):
        '''
        更新
        @param table_name:
        @param where: sql完整的条件，如 id=2 and data=test
        @param values: dict
        @return:
        '''
        table_name = self.escape(table_name)
        with contextlib.suppress(KeyError):
            values.pop('add_time')
        values.update({
            'insert_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        _key_values = ", ".join([
            "%s = %s" % (self.escape(k), self.placeholder) for k in values
        ])
        sql_query = "UPDATE %s SET %s WHERE %s" % (table_name, _key_values, where)

        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query, list(itervalues(values)))
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f"更新数据失败:{values}, {e}")
            return []
        finally:
            connection.close()

    def delete(self, table_name, where=""):
        '''
        删除
        @param table_name:
        @param where: sql完整的条件，如 id=2 and data=test
        @return:
        '''
        table_name = self.escape(table_name)
        sql_query = "DELETE FROM %s" % table_name
        if where:
            sql_query += " WHERE %s" % where

        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f"删除失败:{table_name}, {e}")
            return []
        finally:
            connection.close()

    def add_replace(self, table_name, **values):
        '''
        插入或更新，存在更新，反之插入
        @param table_name:
        @param where:
        @param values:
        @return:
        '''
        if not values:
            return
        _table_name = self.escape(table_name)
        values.update({
            'insert_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        _keys = ", ".join((self.escape(k) for k in values))
        _values = ", ".join([self.placeholder, ] * len(values))
        sql_query = "REPLACE INTO %s (%s) VALUES (%s)" % (table_name, _keys, _values)
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query, list(itervalues(values)))
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f'插入数据失败：{values}，table_name:{table_name},error:{e}')
            return []
        finally:
            connection.close()

    def insert_update(self, table_name, where='1=0', **values):
        '''
        插入或更新，存在更新，反之插入
        @param table_name:
        @param where:
        @param values:
        @return:
        '''
        query = self.select(table_name=table_name, where=where)
        if query:
            self.update(table_name=table_name, where=where, **values)
        else:
            self.insert(table_name=table_name, **values)

    def insert_update_with_updatetime(self, table_name, where='1=0', **values):
        query = self.select(table_name=table_name, where=where)
        connection = self.pool.connection()
        if query:
            table_name = self.escape(table_name)
            with contextlib.suppress(KeyError):
                values.pop('add_time')
            values.update({
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            _key_values = ", ".join([
                "%s = %s" % (self.escape(k), self.placeholder) for k in values
            ])
            sql_query = "UPDATE %s SET %s WHERE %s" % (table_name, _key_values, where)
            try:
                with connection.cursor(DictCursor) as cursor:
                    cursor.execute(sql_query, list(itervalues(values)))
                    connection.commit()
            except pymysql.MySQLError as e:
                logger.error(f'插入数据失败：{values}，table_name:{table_name},error:{e}')
                return []
            finally:
                connection.close()
        else:
            table_name = self.escape(table_name)
            if values:
                values.update({
                    'insert_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                _keys = ", ".join((self.escape(k) for k in values))
                _values = ", ".join([self.placeholder, ] * len(values))
                sql_query = "INSERT INTO %s (%s) VALUES (%s)" % (table_name, _keys, _values)
            else:
                sql_query = "INSERT INTO %s DEFAULT VALUES" % table_name
            try:
                with connection.cursor(DictCursor) as cursor:
                    if values:
                        cursor.execute(sql_query, list(itervalues(values)))
                    else:
                        cursor.execute(sql_query)
                    connection.commit()
            except pymysql.MySQLError as e:
                logger.error(f'插入数据失败：{values}，table_name:{table_name},error:{e}')
                return []
            finally:
                connection.close()

    def insert_pandas(self, df, table_name):
        """
        将 DataFrame 中的数据插入到 MySQL 数据库中的指定表中，并根据主键更新数据
        :param df:
        :param table_name:
        :return:
        """
        new_df = df.where(pd.notnull(df), None) # 把dataFrame中nan转为None
        list_of_dicts = new_df.to_dict(orient='records')
        connection = self.pool.connection()
        try:
            for data in list_of_dicts:
                _table_name = self.escape(table_name)
                _keys = ", ".join((self.escape(k) for k in data))
                _values = ", ".join([self.placeholder, ] * len(data))
                sql_query = "REPLACE INTO %s (%s) VALUES (%s)" % (table_name, _keys, _values)
                _sql_value = [None if x == "" else x for x in list(itervalues(data))]
                all_none = all(x is None for x in _sql_value)  # 过滤空行
                if not all_none:
                    try:
                        with connection.cursor(DictCursor) as cursor:
                            cursor.execute(sql_query, _sql_value)
                            connection.commit()
                    except Exception as e:
                        logger.error(
                            f'插入数据失败：{json.dumps(data, ensure_ascii=False)}，table_name:{table_name},error:{e}')
        except Exception as e:
            logger.error(
                f'插入数据失败:table_name:{table_name},error:{e}')
        finally:
            connection.close()

    def truncate_data_from_table(self, table_name):
        logger.info(f'删除数据{table_name}')
        sql_query = f"""TRUNCATE TABLE {table_name}"""
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f'清除表数据失败，table_name:{table_name},error:{e}')
            return []
        finally:
            connection.close()

    def delete_data_from_table(self, table_name, where=None):
        logger.info(f'删除数据{table_name}')
        sql_query = f"""DELETE FROM {table_name}"""
        if where:
            sql_query += " WHERE %s" % where
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                connection.commit()
        except pymysql.MySQLError as e:
            logger.error(f'清除表数据失败，table_name:{table_name},error:{e}')
            return []
        finally:
            connection.close()

    def show_databases(self):
        """
        获取数据库列表
        """
        sql_query = "SHOW DATABASES"
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                rest = cursor.fetchall()
                return [item.get('Database') for item in rest] if rest else []
        except pymysql.MySQLError as e:
            logger.error(f'获取数据库列表失败,error:{e}')
            return []
        finally:
            connection.close()

    def show_tables(self, database_name: str = None):
        """
        获取指定数据库中的所有表
        @param database_name: 数据库名称，默认为当前连接的数据库
        @return: 表名列表
        """
        if database_name:
            sql_query = f"SHOW TABLES FROM {self.escape(database_name)}"
        else:
            sql_query = "SHOW TABLES"
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                rest = cursor.fetchall()
                return [list(item.values())[0] for item in rest] if rest else []
        except pymysql.MySQLError as e:
            logger.error(f'获取数据库列表失败,error:{e}')
            return []
        finally:
            connection.close()

    def show_columns(self, table):
        '''

        @param table:
        @return:
        '''
        sql_query = f"SHOW COLUMNS FROM {self.escape(table)}"
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql_query)
                rest = cursor.fetchall()
                return [item.get("Field") for item in rest] if rest else []
        except pymysql.MySQLError as e:
            logger.error(f'获取数据库列表失败,error:{e}')
            return []
        finally:
            connection.close()

    def batch_update_only_existing(self, table_name: str, data_list: List[Dict[str, Any]], steep=1000):
        '''
        批量更新（仅更新已存在记录）,只更新存在的数据，不存在的数据忽略，使用 executemany
        :param table_name:
        :param data_list:
        :param steep:
        :return:
        '''
        if not data_list:
            return
        _data_list = [i for i in data_list if i and isinstance(i, dict)]
        if not _data_list:
            return
        primary_keys = self.get_primary_key(table_name)
        if not primary_keys:
            raise ValueError(f"表 `{table_name}` 没有主键，无法更新")
        all_columns = list(_data_list[0].keys())
        update_columns = [col for col in all_columns if col not in primary_keys]
        if not update_columns:
            return
        set_clause = ", ".join([f"`{k}` = {self.placeholder}" for k in update_columns])
        where_clause = " AND ".join([f"`{k}` = {self.placeholder}" for k in primary_keys])
        sql = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                for i in range(0, len(_data_list), steep):
                    batch = _data_list[i:i + steep]
                    # 构建参数列表
                    param_list = []
                    for row in batch:
                        try:
                            params = [row[col] for col in update_columns] + [row[pk] for pk in primary_keys]
                            param_list.append(params)
                        except KeyError as e:
                            logger.warning(f"跳过缺少字段的行: {e}, row={row}")
                    start = time.time()
                    cursor.executemany(sql, param_list)
                    duration = time.time() - start
                    logger.info(f"[Batch {i // steep + 1}] 更新 {len(param_list)} 条，用时 {duration:.4f}s")
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.exception(f"批量更新失败：{e}")
        finally:
            connection.close()

    # insert 主键存在只更新插入时间   replace 完全替换,整条记录所有删除后新增
    @retry(tries=3, delay=3, backoff=2)
    def batch_insert_replace(self, table_name: str, data_list: List[Dict[str, Any]], steep=1000, method='replace'):
        if not data_list:
            return
        _data_list = [i for i in data_list if i and isinstance(i, dict)]
        if not _data_list:
            return

        # 统一字段集合（保证所有字段都能覆盖）
        all_columns = set()
        for d in _data_list:
            all_columns.update(d.keys())
        columns = list(all_columns)

        # 判断是否需要添加 insert_time 字段
        add_insert_time = 'insert_time' not in columns
        if add_insert_time:
            columns.append('insert_time')

        _keys = ", ".join(self.escape(k) for k in columns)
        _values = ", ".join([self.placeholder] * len(columns))

        if method == 'insert':
            sql = f"""
                INSERT INTO {self.escape(table_name)} ({_keys}) 
                VALUES ({_values}) 
                ON DUPLICATE KEY UPDATE insert_time = VALUES(insert_time)
            """
        else:
            sql = f"REPLACE INTO {self.escape(table_name)} ({_keys}) VALUES ({_values})"

        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                for number in range(0, len(_data_list), steep):
                    _tmp_data = _data_list[number:number + steep]
                    values_list = []
                    now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for item in _tmp_data:
                        row = [item.get(col) for col in columns]
                        if add_insert_time:
                            row[columns.index('insert_time')] = now_time
                        values_list.append(row)

                    cursor.executemany(sql, values_list)
                    connection.commit()
                    logger.info(f"数据表{table_name}成功插入 {len(_tmp_data)} 条数据")
        except pymysql.err.IntegrityError as e:
            error_code = e.args[0]
            error_msg = e.args[1]
            if error_code != 1062:
                logger.error(f"MySQL完整性错误：{error_msg}")
                connection.rollback()
        except Exception as e:
            logger.error(f"数据表{table_name}批量插入失败,{e}")
            connection.rollback()
            raise Exception(f'数据表{table_name}批量插入失败,{e}{data_list}')
        finally:
            connection.close()

    @retry(tries=3, delay=3, backoff=2)
    def batch_insert_ignore(
        self,
        table_name: str,
        data_list: List[Dict[str, Any]],
        steep: int = 1000,
    ) -> None:
        """
        批量插入：与主键或唯一索引冲突的行忽略，其余行插入。

        使用 ``INSERT IGNORE``；要求表上至少存在主键或唯一约束，否则
        MySQL 无法识别「重复」语义。

        :param table_name: 目标表名
        :param data_list: 多行字典数据
        :param steep: 每批 ``executemany`` 的最大行数
        :return: None
        :raises Exception: 执行失败时抛出（非重复类错误）
        """
        if not data_list:
            return
        _data_list = [i for i in data_list if i and isinstance(i, dict)]
        if not _data_list:
            return

        all_columns = set()
        for d in _data_list:
            all_columns.update(d.keys())
        columns = list(all_columns)

        add_insert_time = "insert_time" not in columns
        if add_insert_time:
            columns.append("insert_time")

        _keys = ", ".join(self.escape(k) for k in columns)
        _values = ", ".join([self.placeholder] * len(columns))
        sql = "INSERT IGNORE INTO %s (%s) VALUES (%s)" % (
            self.escape(table_name),
            _keys,
            _values,
        )

        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                for number in range(0, len(_data_list), steep):
                    _tmp_data = _data_list[number : number + steep]
                    values_list = []
                    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for item in _tmp_data:
                        row = [item.get(col) for col in columns]
                        if add_insert_time:
                            row[columns.index("insert_time")] = now_time
                        values_list.append(row)
                    cursor.executemany(sql, values_list)
                    connection.commit()
                    logger.info(
                        "数据表 %s 批量 INSERT IGNORE 提交 %s 条",
                        table_name,
                        len(_tmp_data),
                    )
        except pymysql.err.IntegrityError as e:
            error_code = e.args[0]
            error_msg = e.args[1]
            if error_code != 1062:
                logger.error("MySQL 完整性错误：%s", error_msg)
                connection.rollback()
        except Exception as e:
            logger.error("数据表 %s 批量 INSERT IGNORE 失败: %s", table_name, e)
            connection.rollback()
            raise Exception("数据表 %s 批量 INSERT IGNORE 失败: %s" % (table_name, e))
        finally:
            connection.close()

    def _primary_key_cache_key(self, table_name: str) -> str:
        """
        Redis 缓存键（避免与业务里同名 key 冲突）。

        :param table_name: 表名
        :return: 缓存键字符串
        """
        return "mysql:primary_key:v1:%s" % (table_name,)

    def _fetch_primary_key_from_db(self, table_name: str) -> List[str]:
        """
        从当前库解析表的主键列名（有序）。

        先用 ``SHOW KEYS``（元组下标与 MySQL 一致）；若无行再用
        ``INFORMATION_SCHEMA``（兼容表名大小写、列名元数据差异）。

        :param table_name: 表名
        :return: 主键列名列表；无主键时为空列表
        """
        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SHOW KEYS FROM %s WHERE Key_name = 'PRIMARY'"
                    % (self.escape(table_name),)
                )
                rows = cursor.fetchall() or []
                if rows:
                    # (Table, Non_unique, Key_name, Seq_in_index, Column_name, ...)
                    rows = sorted(rows, key=lambda t: int(t[3] or 0))
                    return [str(t[4]) for t in rows]
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT COLUMN_NAME AS pk_col
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND LOWER(TABLE_NAME) = LOWER(%s)
                      AND CONSTRAINT_NAME = 'PRIMARY'
                    ORDER BY ORDINAL_POSITION
                    """,
                    (table_name,),
                )
                alt = cursor.fetchall() or []
                return [str(x["pk_col"]) for x in alt]
        finally:
            connection.close()

    def get_primary_key(self, table_name: str) -> List[str]:
        """
        查询表的主键列名并短时缓存。

        不再使用裸表名作为 Redis key；且**不缓存空列表**，避免历史上无主键
        或误查结果被缓存 24 小时后，即使已加主键仍无法 upsert。

        :param table_name: 表名
        :return: 主键列名列表
        """
        cache_key = self._primary_key_cache_key(table_name)
        cache = self.redis.get(cache_key)
        if cache:
            try:
                return json.loads(cache.decode("utf-8"))
            except Exception as e:
                raise ValueError(e) from e

        r = self._fetch_primary_key_from_db(table_name)
        if r:
            self.redis.set(cache_key, json.dumps(r), ex=60 * 60 * 24)
        return r

    @retry(tries=3, delay=3, backoff=2)
    def batch_update_insert(
        self,
        table_name: str,
        data_list: List[Dict[str, Any]],
        step: int = 1000,
        exclude_update_columns: Optional[List[str]] = None,
    ):
        """
        批量 upsert：不存在则插入；与主键或唯一索引冲突则更新列。

        ``exclude_update_columns`` 中的列仍会写入新插入行；仅在冲突后的
        ``UPDATE`` 阶段跳过（适用于首次写入后不再覆盖的字段）。
        主键列始终不参与更新；``insert_time`` 始终不参与更新（与历史行为一致）。

        :param table_name: 目标表名
        :param data_list: 多行字典数据（可按行列集合分组批量执行）
        :param step: 每批 ``executemany`` 的最大行数
        :param exclude_update_columns: 指定不更新的列名列表；``None`` 表示无额外排除
        :return: None
        :raises ValueError: 表无主键时无法 upsert
        """
        if not data_list:
            return

        pk_cols = self.get_primary_key(table_name)
        if not pk_cols:
            raise ValueError(f"表 {table_name} 未检测到主键/唯一索引，无法 upsert")

        skip_update = frozenset(exclude_update_columns or ())

        # 过滤掉空数据
        _data_list = [d for d in data_list if d and isinstance(d, dict)]
        if not _data_list:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 按「字段集合」分组
        groups = defaultdict(list)
        for d in _data_list:
            row = d.copy()
            if "insert_time" not in row:
                row["insert_time"] = now
            keyset = tuple(sorted(row.keys()))
            groups[keyset].append(row)

        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                for cols, rows in groups.items():
                    esc_cols = ", ".join(self.escape(c) for c in cols)
                    placeholders = ", ".join([self.placeholder] * len(cols))

                    # UPDATE：非主键、非 insert_time、且不在排除列表中的列
                    update_cols = [
                        f"{self.escape(c)} = VALUES({self.escape(c)})"
                        for c in cols
                        if c not in pk_cols
                        and c != "insert_time"
                        and c not in skip_update
                    ]
                    if update_cols:
                        dup_clause = ", ".join(update_cols)
                    else:
                        # ON DUPLICATE KEY UPDATE 至少需一项赋值；主键自赋值等价于无改动
                        dup_clause = "{0} = {0}".format(
                            self.escape(pk_cols[0]),
                        )

                    sql = f"""
                        INSERT INTO {self.escape(table_name)} ({esc_cols})
                        VALUES ({placeholders})
                        ON DUPLICATE KEY UPDATE {dup_clause}
                    """

                    # 分批执行
                    for i in range(0, len(rows), step):
                        batch = rows[i : i + step]
                        value_list = [[r[c] for c in cols] for r in batch]
                        cursor.executemany(sql, value_list)
                        connection.commit()
                        logger.info(f"[{table_name}] 成功 upsert {len(batch)} 条数据")
        except pymysql.err.IntegrityError as e:
            logger.error(f"MySQL 完整性错误: {e}")
            connection.rollback()
            raise
        except Exception as e:
            logger.error(f"批量 upsert 失败: {e}")
            connection.rollback()
            raise
        finally:
            connection.close()

    @retry(tries=3, delay=3, backoff=2)
    def batch_insert(self, table_name: str, data_list: List[Dict[str, Any]], steep=20, replace=True):
        """
        批量插入函数
        @param table_name: 要插入数据的表名
        @param data_list: 包含数据的字典列表
        @param steep: 步长，每次入库条数
        @param replace: 是否覆盖更新。True: 冲突则更新(UPSERT)；False: 冲突则跳过(IGNORE)
        """
        if not data_list:
            return

        # 过滤无效数据
        _data_list = [i for i in data_list if i and isinstance(i, dict)]
        if not _data_list:
            return

        # 1. 动态构造 SQL 核心字段
        data = _data_list[0]
        columns = list(data.keys())
        columns.append('insert_time')

        _keys = ", ".join(self.escape(k) for k in columns)
        _values = ", ".join([self.placeholder] * len(columns))

        # 2. 根据 replace 参数决定冲突处理策略
        if replace:
            # 模式：ON DUPLICATE KEY UPDATE (存在则更新)
            _updates = ", ".join(
                [f"{self.escape(k)} = VALUES({self.escape(k)})" for k in columns if k != 'insert_time'])
            sql = f"INSERT INTO {self.escape(table_name)} ({_keys}) VALUES ({_values}) ON DUPLICATE KEY UPDATE {_updates}"
        else:
            # 模式：INSERT IGNORE (存在则跳过)
            sql = f"INSERT IGNORE INTO {self.escape(table_name)} ({_keys}) VALUES ({_values})"

        # 3. 执行入库逻辑
        connection = self.pool.connection()
        _tmp_data = []
        try:
            with connection.cursor() as cursor:
                for number in range(0, len(_data_list), steep):
                    # 每一批次获取最新的时间戳（确保入库时间的相对准确性）
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _tmp_data = _data_list[number:number + steep]

                    # 组装数据：将字典的值与时间戳合并
                    batch_values = [
                        [
                            current_time if col == "insert_time" else item.get(col, None)
                            for col in columns
                        ]
                        for item in _tmp_data
                    ]

                    cursor.executemany(sql, batch_values)
                    connection.commit()

                    action_str = "插入或更新" if replace else "插入(跳过重复)"
                    logger.info(f"成功{action_str} {len(_tmp_data)} 条数据")
        except Exception as e:
            logger.error(f"批量操作失败, 错误数据样例: {json.dumps(_tmp_data[:1])}, 异常: {e}")
            connection.rollback()
        finally:
            connection.close()

    def _infer_data_type(self, value: Any) -> str:
        '''
        推断数据类型
        @param value: 字段值
        @return: 对应的 SQL 数据类型
        '''
        if isinstance(value, int):
            return 'INT'
        elif isinstance(value, float):
            return 'DECIMAL(10,2)'
        elif isinstance(value, str):
            if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', value):  # DateTime 格式
                return 'DATETIME'
            elif len(value) > 255:
                return 'TEXT'
            else:
                return 'VARCHAR(255)'
        elif isinstance(value, bool):
            return 'TINYINT'
        else:
            return 'TEXT'

    def execute_sql(self, sql: str, value=None):
        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                if value:
                    cursor.execute(sql, value)
                else:
                    cursor.execute(sql)
                connection.commit()
                return cursor
        except Exception as e:
            connection.rollback()
            logger.error(e)
            return None
        finally:
            connection.close()

    def batch_execute_sql(self, sql: str, value_list: list):
        """
        批量执行 SQL，提高效率
        :param sql: 带参数的 SQL 语句
        :param value_list: 参数列表，每个元素是一个 tuple
        """
        if not value_list:
            return

        connection = self.pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.executemany(sql, value_list)
            connection.commit()
            logger.info(f"批量执行成功，共 {len(value_list)} 条")
        except Exception as e:
            connection.rollback()
            logger.error(f"批量执行 SQL 失败: {e}")
        finally:
            connection.close()

    def select_by_sql(self, sql):
        connection = self.pool.connection()
        try:
            with connection.cursor(DictCursor) as cursor:
                cursor.execute(sql)
                rest = cursor.fetchall()
                connection.commit()
                return rest if rest else []
        except pymysql.MySQLError as e:
            logger.error(f"查询失败: sql:{sql},错误：{e}")
            return []
        finally:
            connection.close()


if __name__ == "__main__":
    # MySQL 连接配置

    # 创建实例
    db = MysqlProjectDB()
    rest = db.get_primary_key('fs_discover_code_channel_map')
    print(rest)
