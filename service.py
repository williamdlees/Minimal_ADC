from flask_restx import Namespace, Resource
from flask import current_app
STATUS_OK = 200

# Create a Namespace
ns = Namespace('service', description='Service operations')

@ns.route('/')
class ServiceStatus(Resource):
    def get(self):
        current_app.logger.info('Service status was reached')
        return {"result": "success"} ,STATUS_OK

@ns.route('/info')
class ServiceInfo(Resource):
    def get(self):
        current_app.logger.info('Service information was reached')
        return current_app.config["API_INFORMATION"] , STATUS_OK
