# -*- coding: utf-8 -*-
# @Time    : 2022/3/3 16:07
import multiprocessing

bind = "0.0.0.0:8080"
backlog = 512  # 监听队列数量，64-2048
# chdir = '/data/ROOT/shopify'  #gunicorn要切换到的目的工作目录
# worker_class = 'gtheard' #使用gevent模式，还可以使用sync 模式，默认的是sync模式
worker_class = 'uvicorn.workers.UvicornWorker'  # 使用gevent模式，还可以使用sync 模式，默认的是sync模式
workers = 10  # multiprocessing.cpu_count()    #进程数
threads = 1  # multiprocessing.cpu_count()*4 #指定每个进程开启的线程数
loglevel = 'info'  # 日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
# access_log_format = '%(t)s %(p)s %(h)s "%(r)s" %(s)s %(L)s %(b)s %(f)s" "%(a)s"'
# accesslog、errorlog日志文件可以写到文件
accesslog = "/data/logs/api_access.log"  # 访问日志文件
errorlog = "/data/logs/api_error.log"  # 错误日志文件
# accesslog = "-"  #访问日志文件，"-" 表示标准输出
# errorlog = "-"   #错误日志文件，"-" 表示标准输出

proc_name = 'scraper_api'  # 进程名
# daemon = True  # 守护进程
# reload = True  # 自启动
