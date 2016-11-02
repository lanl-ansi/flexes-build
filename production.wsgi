import os
import site
import sys

# Add virtualenv site packages
site.addsitedir(os.path.join(os.path.dirname(__file__), 'env/lib64/python3.5/site-packages'))
 
# Path of execution
sys.path.insert(0, '/var/www/lanlytics-api')

# Fired up virtualenv before include application
activate_this = os.path.expanduser(os.path.join(os.path.dirname(__file__), 'env/bin/activate_this.py'))
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

from app import app as application
