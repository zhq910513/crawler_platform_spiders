# -*- coding: utf-8 -*-
# @Time    : 2024/03/25 16:07

import os, socket
import sys
from urllib.parse import quote

from sqlalchemy.ext.declarative import declarative_base
from settings import PY_ENV

if PY_ENV == 1:
    from settings.dev import *
elif PY_ENV == 2:
    from settings.test import *
else:
    from settings.prod import *
BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(BASE_DIR, 'statics', "google_service.json")
os.environ["AWS_ACCESS_KEY_ID"] = ""
os.environ["AWS_SECRET_ACCESS_KEY"] = ""
os.environ["AWS_DEFAULT_REGION"] = ""

LOCAL_ID = socket.gethostbyname(socket.gethostname())
# 创建对象的基类:
Base = declarative_base()
# base dir

# db_session_instance = sessionmaker(bind=SQLALCHEMY_ENGINE, autocommit=False, autoflush=False)

# 飞书告警配置
FEISHU_WARNING_USER = ""
WARNING_INTERVAL = 60 * 10
FEISHU_WARNING_ALL = False  # 是否提示所有人， 默认为False
WARNING_LEVEL = "DEBUG"  # 报警级别， DEBUG / INFO / ERROR
FEISHU_USER = {}

# oss domain
OSS_DOMAIN = ""
REDIS_IMAGE_UPLOAD = ""

