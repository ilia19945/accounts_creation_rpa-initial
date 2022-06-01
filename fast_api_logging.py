import datetime
import logging


logger = logging.getLogger()

formatter = logging.Formatter(fmt='{asctime} - {levelname} - {name} - {module}:{funcName}:{lineno} - {message}', style='{')

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

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.setLevel('DEBUG')


# filters | not used for now
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
# console_handler.addFilter(InfoFilter())
# file_handler.addFilter(DebugFilter())
# file_handler.addFilter(ErrorCriticalFilter())
# can't connect more than 1 filter!

