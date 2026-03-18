#!/usr/bin/python3
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(format=None)

try:
    # get sentinelone cloud output path
    output_dir = Path(os.environ.get('S1_OUTPUT_DIR_PATH', '/tmp'))

    # echo the first parameter
    try:
        arg = sys.argv[1]
        print('param received:', arg)
    except IndexError:
        print('no param received')

    # test file writing
    with open(output_dir / 'file.txt', 'w') as file:
        file.write('some text')

    # logging to stdout
    logging.info('A file.txt has been written in', str(output_dir))

    # logging to stderr
    logging.error('Something wrong happened!')

except Exception as e:
    logging.critical(e)
    sys.exit(1)
