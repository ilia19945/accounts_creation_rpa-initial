import logging

# DOESN'T WORK ON SERVER, DUT TO 4GB RAM AND 2 CPU CORE
# from elasticapm import Client
# from elasticapm.handlers.logging import LoggingFilter

logging.basicConfig(level="INFO")
console = logging.StreamHandler()
# console.addFilter(LoggingFilter())
# add the handler to the root logger
logging.getLogger("").addHandler(console)
# client = Client()  # took example from Client() class description, the example on the docunetation doesn't work
