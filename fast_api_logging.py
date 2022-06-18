import datetime
import logging

# from elasticapm.contrib.starlette import make_apm_client
# from elasticapm.handlers.logging import LoggingFilter, Formatter

'''
    An unsuccessful experiment with ELK. Irrelevant anymore. will keep all code commented for possible future development.
    Currently everything will be logged just to the python console and to the log_date.log files.
'''

# apm_config = {
#     'SERVICE_NAME': 'mainfastapi',
#     'SERVER_URL': 'http://localhost:8200',
#     'ENVIRONMENT': 'dev',
#     'GLOBAL_LABELS': 'platform=MainFastApi, application=AccountCreationAutomation',
#     'CAPTURE_HEADERS': True,
#     'CAPTURE_BODY': 'all',
#     'LOG_LEVEL': 'info',
#     'LOG_FILE': 'C:\PythonProjects\Fastapi\local_logs\log.txt',
#     'LOG_FILE_SIZE': '100mb'
# }
#
# apm = make_apm_client(apm_config)


logger = logging.getLogger()

formatter = logging.Formatter(fmt='{asctime} - {levelname} - {name} - {module}:{funcName}:{lineno} - {message}', style='{')
# formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# DEBUG 10
# INFO 20
# WARNING 30
# ERROR 40
# CRITICAL 50

# console output
console_handler = logging.StreamHandler()
console_handler.setLevel('DEBUG')
console_handler.setFormatter(formatter)

# file logging
file_handler = logging.FileHandler(filename=f'C:\PythonProjects\Fastapi\local_logs\\{datetime.date.today().strftime("%m-%d-%Y")}.log', mode='a')
file_handler.setLevel('INFO')
file_handler.setFormatter(formatter)
# file_handler.addFilter(LoggingFilter()) #

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.setLevel('DEBUG')

# filters are not used for now
class InfoFilter(logging.Filter):
    def filter(self, record):
        # print(record.__dict__)
        return record.levelname == 'INFO'
        # return True


class DebugFilter(logging.Filter):
    def filter(self, record):
        return record.levelname == 'DEBUG'


class ErrorCriticalFilter(logging.Filter):
    def filter(self, record):
        return record.levelname in ['ERROR', 'CRITICAL']

# filters are not connected
# https://docs.python.org/3/library/logging.html
# https://stackoverflow.com/questions/879732/logging-with-filters
# console_handler.addFilter(InfoFilter())
# file_handler.addFilter(DebugFilter())
# file_handler.addFilter(ErrorCriticalFilter())
# can't connect more than 1 filter!


def info(msg):
    # apm.capture_message(msg)
    logging.info(msg)


def debug(msg):
    # apm.capture_message(msg)
    logging.debug(msg)


def error(msg):
    # apm.capture_exception(msg)
    logging.error(msg, exc_info=True)
