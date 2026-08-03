# -*- coding: utf-8 -*-
# @Time    : 2024/7/19 14:20
# @Description :

import base64

from databases.sql.mysqldb import MysqlProjectDB


class UFLEplusssBase(object):
    account_list = []

    def __init__(self):
        self.db = MysqlProjectDB()
        self.page_size = 200

    @staticmethod
    def auth():
        return base64.b64encode("ulike202407:ulike202407".encode('utf-8')).decode('utf-8')
