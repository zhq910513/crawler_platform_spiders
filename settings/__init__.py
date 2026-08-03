# -*- coding: utf-8 -*-
# @Time    : 2022/04/02 18:02
import os

PY_ENV = int(os.getenv("SPIDERDEV", 3))  # 1 dev 2 test,3,prod
# PY_ENV = 2