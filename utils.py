import os
import shutil
import json
from repertoire import *
from flask import current_app

# Create 'log' and 'studies' directories if they don't exist and copy studies from a specified source to destination
def before_server_loads(config):
    if not os.path.exists(r'/log'):
        os.makedirs(r'/log')
    
    if not os.path.exists(r'/studies'):
        os.makedirs(r'/studies')
