# -*- coding: utf-8 -*-
# @Time    : 2024/5/6 17:04
# @Description :


from __future__ import unicode_literals, division, absolute_import

from plugins.log import logger
import mysql.connector
from retry import retry

from settings.base import *
# logger = logging.getLogger(__name__)


class SqlError(Exception):
    pass


class BaseDB(object):
    placeholder = '%s'
    maxlimit = -1

    def __init__(self, host=MYSQL_HOST, port=MYSQL_PORT, database=MYSQL_DB,
                 user=MYSQL_USER, passwd=MYSQL_PWD):
        '''
        MYSQL_USER, _PWD, MYSQL_HOST, MYSQL_PORT, MYSQL_DB
        @param host:
        @param port:
        @param database:
        @param user:
        @param passwd:
        '''
        self.database_name = database
        self.conn_sql(host, port, database, user, passwd)

    @retry(tries=3)
    def conn_sql(self, host, port, database,
                 user, passwd):
        self.conn = mysql.connector.connect(user=user, password=passwd,
                                            host=host, port=port, autocommit=True)
        if database not in [x[0] for x in self._execute('show databases')]:
            self._execute('CREATE DATABASE %s' % self.escape(database))
        self.conn.database = database

    @staticmethod
    def escape(string):
        return '`%s`' % string

    @property
    def dbcur(self):
        '''
        @return:
        '''
        try:
            if self.conn.unread_result:
                self.conn.get_rows()
            return self.conn.cursor()
        except (mysql.connector.OperationalError, mysql.connector.InterfaceError):
            self.conn.ping(reconnect=True)
            self.conn.database = self.database_name
            return self.conn.cursor()

    def _execute(self, sql_query, values=[]):
        '''
        sql执行
        @param sql_query:
        @param values:
        @return:
        '''
        dbcur = self.dbcur
        dbcur.execute(sql_query, values)
        return dbcur
