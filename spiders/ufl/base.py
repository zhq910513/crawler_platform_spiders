# -*- coding: utf-8 -*-
# @Time    : 2024/5/20 14:21
# @Description :

from curl_cffi import requests

from databases.sql.sql_for_obj import MysqlProjectDB
from plugins.log import logger
from plugins.redis_ctl import RedisCtrl


# https://member.eplusss.com/#/cus/store-in


class UFLBase(object):
    def __init__(self, *args, **kwargs):
        self.db = MysqlProjectDB()
        self.redis = RedisCtrl()
        self.redis_key = None
        self.session = None

    def get_account_setting(self, account):
        self.redis_key = f'ufl_{account["username"]}'

    @staticmethod
    def generate_headers():
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://member.eplusss.com',
            'priority': 'u=1, i',
            'referer': 'https://member.eplusss.com/',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'timezone': 'GMT+8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

    def get_session(self):
        session = requests.Session()
        headers = self.generate_headers()
        session.headers.clear()
        session.headers.update(headers)
        return session

    def get_response(self, url, params=None, json_data=None, data=None, allow_redirects=False, retry=0):
        try:
            if not json_data and not data:
                response = self.session.get(url=url, params=params, allow_redirects=allow_redirects, verify=False)
            else:
                response = self.session.post(url=url, params=params, json=json_data, data=data,
                                             allow_redirects=allow_redirects, verify=False)
            return response
        except Exception as e:
            if retry < 3:
                return self.get_response(url=url, params=params, json_data=json_data, data=data,
                                         allow_redirects=allow_redirects, retry=retry + 1)
            else:
                logger.error(e)

    def login(self, account):
        if self.redis.exists(self.redis_key):
            self.redis.delete(self.redis_key)

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://member.eplusss.com',
            'priority': 'u=1, i',
            'referer': 'https://member.eplusss.com/',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        self.session.headers.clear()
        self.session.headers.update(headers)

        json_data = {
            'username': account["username"],
            'password': account["password"],
        }

        response = self.get_response('https://member.eplusss.com:8445/index/login', json_data=json_data)
        if response.json()["message"] == "login successfully":
            authorization = response.json()["data"]["token"]
            self.redis.set(self.redis_key, authorization, ex=60 * 60 * 24 * 5)
            logger.info(f"ufl 获取登录 headers authorization 成功!")
        else:
            raise ValueError(f"ufl 登陆失败, 原因: {response.text}")
