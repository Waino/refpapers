import logging
from pathlib import Path

logger = logging.getLogger('refpapers')
logger.setLevel(logging.INFO)

# console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)

formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)


def add_file_handler(log_path: Path):
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s/%(funcName)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
