import logging

logger = logging.getLogger('refpapers')
logger.setLevel(logging.INFO)

# console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)

formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)

# file handler
fh = logging.FileHandler('FIXME.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s/%(funcName)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
