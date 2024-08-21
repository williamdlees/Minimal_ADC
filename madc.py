# Configuration settings
import datetime

DEBUG = True
HOST = '127.0.0.1'
PORT = 5000


# API information
API_VERSION = '1.0'
API_TITLE = 'Minimal ADC API'
API_DESCRIPTION = 'An API for accessing ADC data'
API_INFORMATION = {"version": API_VERSION,
                    "title": API_TITLE,
                    "description": API_DESCRIPTION,
                }


WEEKLY_LIMIT = 100 * 1024 * 1024 * 1024  # 100GB in bytes
USAGE= {
    'start_date': datetime.datetime.now(),
    'bytes_transferred': 0
}

USAGE_FILE_PATH=r'/usage.json'
#USAGE_FILE_PATH=r'C:\Users\yaniv\Desktop\work\minimal_adc\usage.json'
JUST_UPLOADS_APP=True
FIRST_LOAD=True

#Paths
#STUDIES_PATH = r'C:\Users\yaniv\Desktop\work\minimal_adc\studies'
STUDIES_PATH = r'/studies/'
