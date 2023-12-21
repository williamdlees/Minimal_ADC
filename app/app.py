from flask import Flask, app
from flask_restx import Api
import logging
from repertoire import create_repertoire_map, repertoire_ns, rearrangement_ns
from service import ns as service_ns
from utils import before_server_loads


logging.basicConfig(level=logging.INFO)


def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('madc.py')# Load configuration from a file
    app.logger.info('Starting the application...')

    # Create an API instance and bind it to the Flask application
    api = Api(app, title='Minimal ADC API', version='1.0', description='')

    # Add namespaces to the Api instance
    api.add_namespace(service_ns, path='/airr/v1')
    api.add_namespace(repertoire_ns, path='/airr/v1/repertoire')
    api.add_namespace(rearrangement_ns, path='/airr/v1/rearrangement')
    try:
        before_server_loads(app.config)
        create_repertoire_map(app.config["STUDIES_PATH"])
    except Exception as e:
        print(e)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])



