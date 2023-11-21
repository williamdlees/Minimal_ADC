from flask import Flask
from flask_restx import Api
import logging
from repertoire import create_repertoire_map, repertoire_ns, rearrangement_ns
from service import ns as service_ns

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


app.config.from_pyfile('madc.py')# Load configuration from a file

# Create an API instance and bind it to the Flask application

app.logger.info('Starting the application...')
api = Api(app, title='Minimal ADC API', version='1.0', description='')

# Add namespaces to the Api instance
api.add_namespace(service_ns, path='/airr/v1')
api.add_namespace(repertoire_ns, path='/airr/v1/repertoire')
api.add_namespace(rearrangement_ns, path='/airr/v1/rearrangement')



if __name__ == '__main__':
    create_repertoire_map(app.config["STUDIES_PATH"])    
    app.run(debug=app.config['DEBUG'])
