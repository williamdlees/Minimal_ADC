from flask_restx import Namespace, Resource, fields
from flask import request, current_app, send_file
import os
import json
import datetime
from json import JSONEncoder

repertoire_map = None
repertoire_ns = Namespace('repertoire', description='Repertoire operation repertoire_ns')
rearrangement_ns = Namespace('rearrangement', description='Repertoire operation rearrangement_ns')

# Define models for Swagger documentation
content_model = repertoire_ns.model('Content', {
    'field': fields.String(required=True, description='Filter field name, only "study_id" is supported', enum=['study_id']),
    'value': fields.String(required=True, description='Value to filter by', example="PRJEB26509_IGH")
})

filters_model = repertoire_ns.model('Filters', {
    'op': fields.String(required=True, description='Filter operation, only "=" is supported', enum=['=']),
    'content': fields.Nested(content_model, required=True)
})

repertoire_query_model = repertoire_ns.model('RepertoireQuery', {
    'filters': fields.Nested(filters_model),
    'fields': fields.List(fields.String,
                          description='List of fields to include in the response',
                          example=["repertoire_id", "subject.species.id", "subject.subject_id", "sample.pcr_target.pcr_target_locus"])
})

# Define models for rearrangement
rearrangement_content_model = rearrangement_ns.model('RearrangementContent', {
    'field': fields.String(required=True, description='Filter field name, only "repertoire_id" is supported', enum=['repertoire_id']),
    'value': fields.Raw(required=True, description='Value to filter by, can be a string or array of strings', example=["100_IGH"])
})

rearrangement_filters_model = rearrangement_ns.model('RearrangementFilters', {
    'op': fields.String(required=True, description='Filter operation', enum=['in', '=']),
    'content': fields.Nested(rearrangement_content_model, required=True)
})

rearrangement_query_model = rearrangement_ns.model('RearrangementQuery', {
    'filters': fields.Nested(rearrangement_filters_model, required=True),
    'format': fields.String(description='Response format, only "tsv" is supported', enum=['tsv'])
})


class DateTimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
   

def decode_datetime(dct):
    for key, value in dct.items():
        if isinstance(value, str) and value.endswith('Z'):
            try:
                dct[key] = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass
        elif isinstance(value, str):
            try:
                dct[key] = datetime.datetime.fromisoformat(value)
            except ValueError:
                pass
    return dct


# check whether the download limit recorded in usage.json has been exceeded
# if usage.json does not exist, create it
# if usage.json exists and the a week has passed since its creation, reset the usage to 0


def check_download_limit():
    if not os.path.exists(current_app.config['USAGE_FILE_PATH']):
        with open(current_app.config['USAGE_FILE_PATH'], 'w') as file:
            current_usage = {'timestamp': datetime.datetime.now(), 'usage': 0}
            json.dump(current_usage, file, indent=4, cls=DateTimeEncoder)

    with open(current_app.config['USAGE_FILE_PATH'], 'r') as file:
        current_usage = json.load(file, object_hook=decode_datetime)
        now = datetime.datetime.now()

        # Reset the usage if the week has passed
        if now - current_usage['timestamp'] > datetime.timedelta(days=7):
            current_usage = {'timestamp': datetime.datetime.now(), 'usage': 0}
            with open(current_app.config['USAGE_FILE_PATH'], 'w') as file:
                json.dump(current_usage, file, indent=4, cls=DateTimeEncoder)

        # Check if the file size exceeds the limit
        if current_usage['usage'] > current_app.config['WEEKLY_LIMIT']:
            return False, f"Weekly download limit exceeded (the limit resets in {7 - (now - current_usage['timestamp']).days} days)"

        # Update the usage
        return True, None

    return False, "error"

# update the amount of bytes transferred to take account of the current file size
# this is called immediately after check_download_limit so we do not need to check for a reset


def update_bytes_transferred(file_size):
    with open(current_app.config['USAGE_FILE_PATH'], 'r') as file:
        current_usage = json.load(file, object_hook=decode_datetime)
    
    current_usage['usage'] += file_size

    with open(current_app.config['USAGE_FILE_PATH'], 'w') as file:
        json.dump(current_usage, file, indent=4, cls=DateTimeEncoder)


@repertoire_ns.route('/<string:repertoire_id>')
@repertoire_ns.param('repertoire_id', 'The repertoire identifier')
class RepertoireResource(Resource):
    @repertoire_ns.doc(description='Get information about a specific repertoire')
    @repertoire_ns.response(200, 'Success')
    @repertoire_ns.response(400, 'Error retrieving repertoire information')
    def get(self, repertoire_id):
        current_app.logger.info(f'Repertoire information for {repertoire_id} was reached')
        repertoire_info = []
        metadata_path = self.find_repertoire_path_by_id(repertoire_id)
        if metadata_path is not None:
            repertoire_info = self.get_repertoire_information(metadata_path, repertoire_id)
            if not repertoire_info:
                current_app.logger.error(f'error with finding reperoire information in {metadata_path}')
        else:
            current_app.logger.info(f'{repertoire_id} not found')
            repertoire_info = "Not Found"
        try:
            x = self.get_metadata(repertoire_info, {})
            repertoire_info = list()
            repertoire_info.append(x)

            return {"Info": current_app.config["API_INFORMATION"],
                    "Repertoire": repertoire_info}

        except Exception as e:
            return {"error": str(e)}, 400

    # finding the repertoire metadata path by the repertoire id
    def find_repertoire_path_by_id(self, repertoire_id):
        path = None
        for metadata_path, repertoire_list in repertoire_map.items():
            for repertoire in repertoire_list:
                if repertoire == repertoire_id:
                    path = metadata_path
                    break

        return path

    def get_metadata(self, repertoire_info, request_data):
        fields = request_data.get("fields", [])
        if len(fields) > 0:
            validate_fields(repertoire_info, fields)
            repertoire_info = get_filtered_metadata(repertoire_info, fields)
        return repertoire_info

    # return the repertoire information by the metadata path
    def get_repertoire_information(self, metadata_path, repertoire_id):
        repertoire_info = None
        with open(metadata_path, 'r') as metadata_file:
            data = json.load(metadata_file)
            for repertoire in data["Repertoire"]:
                if repertoire["repertoire_id"] == repertoire_id:
                    repertoire_info = repertoire
                    break

        return repertoire_info


@repertoire_ns.route('')
class RepertoireList(Resource):
    @repertoire_ns.doc(description='Retrieve repertoire list based on optional filters')
    @repertoire_ns.response(200, 'Success')
    @repertoire_ns.response(400, 'Validation Error')
    @repertoire_ns.expect(repertoire_query_model, validate=False)
    def post(self):
        current_app.logger.info('Repertoire list was reached')
        if request.content_length and request.content_length > 0:
            request_data = request.get_json()
            valid, response = self.validate_repertoire_request(request_data)
            if not valid:
                return response, 400

            study_id = response
            study_repertoires = self.filter_repertoires_by_study(study_id)
            try:
                for i in range(len(study_repertoires)):
                    study_repertoires[i] = (self.get_metadata(study_repertoires[i], request_data))

                return {"Info": current_app.config["API_INFORMATION"],
                        "Repertoire": study_repertoires}

            except Exception as e:
                return json.encode({"error": str(e)}), 400

        all_repertoires = self.get_all_repertoires()
        return {"Info": current_app.config["API_INFORMATION"],
                "Repertoire": all_repertoires}

    def get_metadata(self, repertoire_info, request_data):
        fields = request_data.get("fields", [])
        if len(fields) > 0:
            validate_fields(repertoire_info, fields)
            repertoire_info = get_filtered_metadata(repertoire_info, fields)
        return repertoire_info

    def validate_repertoire_request(self, request_data):
        expected_keys = ['filters', 'fields']
        for key in request_data:
            if key not in expected_keys:
                return False, {"Error": f"Unexpected field '{key}' in request"}

        if 'filters' in request_data:
            filters = request_data['filters']
            if 'content' not in filters or 'op' not in filters:
                return False, {"Error": "Missing 'content' or 'op' in filters"}

            expected_filters = ['content', 'op']
            for filter in expected_filters:
                if filter not in expected_filters:
                    return False, {"Error": f"Unexpected filters '{filter}' in request"}

            filter_content = filters['content']
            filter_op = filters['op']

            if 'field' not in filter_content:
                return False, {"Error": "Missing 'field' in filter content"}

            if 'value' not in filter_content:
                return False, {"Error": "Missing 'value' in filter content"}

            expected_content = ['field', 'value']
            for key in filter_content:
                if key not in expected_content:
                    return False, {"Error": f"Unexpected content '{key}' in request"}
            
            if filter_content['field'] != 'study_id':
                return False, {"Error": "Invalid filter field, only 'study_id' is allowed"}

            if filter_op != '=':
                return False, {"Error": "Invalid filter operation, only '=' is allowed"}

            return True, filter_content['value']
        else:
            return True, None

    # finding the right study and returning its repertoires
    def filter_repertoires_by_study(self, study_id):
        study_repertoires = []
        for metadata_path, repertoire_list in repertoire_map.items():
            if study_id is None or study_id in metadata_path:
                study_repertoires.extend(self.get_all_repertoires_by_study_id(metadata_path))
        
        return study_repertoires

    # returning all study's repertoires that available in the server
    def get_all_repertoires_by_study_id(self, metadata_path):
        study_repertoires = []
        with open(metadata_path, 'r') as metadata_file:
            data = json.load(metadata_file)
            for repertoire in data["Repertoire"]:
                study_repertoires.append(repertoire)
        
        return study_repertoires

    # returning all repertoires that available in the server
    def get_all_repertoires(self):
        all_repertoires = []
        for metadata_path, repertoire_list in repertoire_map.items():
            study_repertoires = self.get_all_repertoires_by_study_id(metadata_path)
            for repertoire in study_repertoires:
                all_repertoires.append(repertoire)

        return all_repertoires


# creating a map of metadata-path(key) and list of the repertoires in that(value)
def create_repertoire_map(studies_path):
    global repertoire_map
    print('Creating repertoire map')
    repertoire_log = []
    repertoire_map = {}
    studies_list = [study for study in os.listdir(studies_path)]
    for study in studies_list:
        print(f'Processing study: {study}')
        study_path = os.path.join(studies_path, study)
        metadata_path = os.path.join(study_path, 'metadata.json')
        with open(metadata_path, 'r') as file:
            data = json.load(file)
            repertoire_list = []
            for repertoire in data["Repertoire"]:
                for rep, met in repertoire_log:
                    if rep == repertoire["repertoire_id"]:
                        print(f"*** Duplicate repertoire_id found: {repertoire['repertoire_id']} is in {met} and {metadata_path}")
                else:
                    file_path = metadata_path.replace('metadata.json', f"{repertoire['repertoire_id']}.tsv.gz")
                    if os.path.exists(file_path):
                        repertoire_log.append((repertoire["repertoire_id"], metadata_path))
                    else:
                        print(f"*** Repertoire file not found: {repertoire['repertoire_id']}: {file_path}")
                repertoire_list.append(repertoire["repertoire_id"])
            repertoire_map[metadata_path] = repertoire_list

    print(f'Created repertoire map with {len(repertoire_map)} metadata files and {len(repertoire_log)} repertoires')


def validate_fields(metadata, fields):
    missing_fields = []

    def check_recursive(data, field_path):
        key = field_path[0]
        if isinstance(data, dict):
            if key not in data:
                missing_fields.append('.'.join(field_path))
            elif len(field_path) > 1:
                check_recursive(data[key], field_path[1:])
        elif isinstance(data, list):
            for item in data:
                check_recursive(item, field_path)

    for field in fields:
        field_path = field.split('.')
        check_recursive(metadata, field_path)

    if missing_fields:
        raise Exception(f"incorrect fields - {str(missing_fields)}")


def filter_dict(data, fields):
    if isinstance(data, dict):
        return {key: filter_dict(value, fields) for key, value in data.items() if any(f.startswith(key) for f in fields)}
    elif isinstance(data, list):
        return [filter_dict(item, fields) for item in data]
    else:
        return data


def get_filtered_metadata(metadata, field_list):
    # Split fields into parts to handle nested structures
    fields_split = [field.split('.') for field in field_list]
    
    def filter_recursive(data, fields):
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                # Get relevant sub-fields
                sub_fields = [f[1:] for f in fields if f[0] == key]
                if sub_fields:
                    filtered[key] = filter_recursive(value, sub_fields)
                elif any(f[0] == key for f in fields):
                    filtered[key] = value
            return filtered
        
        elif isinstance(data, list):
            return [filter_recursive(item, fields) for item in data]

        else:
            return data
    
    return filter_recursive(metadata, fields_split)


@rearrangement_ns.route('')
class RearrangementResource(Resource):
    @rearrangement_ns.doc(description='Download rearrangement data for specific repertoire')
    @rearrangement_ns.response(200, 'Success')
    @rearrangement_ns.response(400, 'Validation Error')
    @rearrangement_ns.response(404, 'File not found')
    @rearrangement_ns.response(503, 'Download limit exceeded')
    @rearrangement_ns.expect(rearrangement_query_model, validate=False)
    def post(self):
        in_limit, message = check_download_limit()
        if in_limit:
            if request.content_length > 0:
                request_data = request.get_json()
                valid, response = self.validate_request(request_data)

                if not valid:
                    return response, 400

                else:
                    if 'facets' in request_data:
                        rearrangement_response = self.get_rearrangements_count(response)
                        return {"Info": current_app.config["API_INFORMATION"], "Facet": rearrangement_response}

                    elif 'format' in request_data:
                        if len(response) != 1:
                            return {"Error": "Exactly one repertoire id must be specified"}, 400
                        
                        filepath = self.get_rearrangements_file(response)
                        if filepath:                         
                            update_bytes_transferred(os.path.getsize(filepath))
                            study_id = os.path.split(filepath)[0]
                            study_id = os.path.split(study_id)[1]
                            transfer_file_name = study_id + '_' + os.path.basename(filepath)
                            current_app.logger.info(f'sending {transfer_file_name}')

                            return send_file(filepath, as_attachment=True, download_name=transfer_file_name, mimetype='application/gzip')
                        else:
                            return {"Error": "File not found"}, 404
                        
                    else:
                        return {"Error": "Invalid request format"}, 400

            else:
                return {"Error": "Missing filters"}, 404
        else:
            current_app.logger.info(message)
            return message, 503

    def get_rearrangements_count(self, repertoire_ids):
        current_app.logger.info(f'Rearrangement count was reached with {repertoire_ids}')
        facet_list = []
        for repertoire in repertoire_ids:
            for metadata_path, repertoire_list in repertoire_map.items():
                if repertoire in repertoire_list:
                    with open(metadata_path, 'r') as metadata_file:
                        data = json.load(metadata_file)
                        for file_repertoire in data["Repertoire"]:
                            if file_repertoire["repertoire_id"] == repertoire:
                                facet_list.append(
                                    {
                                        "repertoire_id": repertoire,
                                        "count": 0
                                    }
                                )
        return facet_list

    def get_rearrangements_file(self, repertoire_id):
        if isinstance(repertoire_id, list):
            repertoire_id = repertoire_id[0]
        current_app.logger.info(f'Rearrangement files was reached with {repertoire_id}')
        for metadata_path, repertoire_list in repertoire_map.items():
            if repertoire_id in repertoire_list:
                # Construct the file path for the .tsv.gz file
                filepath = metadata_path.replace('metadata.json', f"{repertoire_id}.tsv.gz")
                print(filepath)
                return filepath

        return None

        current_app.logger.error("No metadata files found in studies database.")
        return None

    def validate_request(self, request_data):
        facets_in_request = True
        format_in_request = True

        expected_keys = ['filters', 'facets', 'format']
        for key in request_data:
            if key not in expected_keys:
                return False, {"Error": f"Unexpected field '{key}' in request"}

        # Check if filters or facets or format are missing
        if 'filters' not in request_data:
            return False, {"Error": "Missing 'filters' in request"}

        if 'facets' not in request_data:
            facets_in_request = False
            if 'format' not in request_data:
                return False, {"Error": "Missing 'facets' in request"}

        if 'format' not in request_data:
            format_in_request = False
            if 'facets' not in request_data:
                return False, {"Error": "Missing 'format' in request"}

        # Validate facets
        if facets_in_request and request_data['facets'] != 'repertoire_id':
            return False, {"Error": "Invalid facets, only 'repertoire_id' is allowed"}

        # Validate format
        if format_in_request and request_data['format'] != 'tsv':
            return False, {"Error": "Invalid format, only 'tsv' is allowed"}

        # Validate filters
        expected_filters = ['content', 'op']
        for filter in expected_filters:
            if filter not in expected_filters:
                return False, {"Error": f"Unexpected filters '{filter}' in request"}

        filter_content = request_data['filters']['content']
        filter_op = request_data['filters']['op']

        # Check if filter content is properly formed
        if not filter_content:
            return False, {"Error": "Missing 'content' in filters"}

        if 'field' not in filter_content:
            return False, {"Error": "Missing 'field' in filter content"}

        if 'value' not in filter_content:
            return False, {"Error": "Missing 'value' in filter content"}

        # Validate specific filter fields
        expected_content = ['field', 'value']
        for content in expected_content:
            if content not in expected_content:
                return False, {"Error": f"Unexpected content '{content}' in request"}

        if filter_content['field'] != 'repertoire_id':
            return False, {"Error": "Invalid filter field, only 'repertoire_id' is allowed"}

        # Validate filter operation
        if filter_op != 'in' and filter_op != '=':
            return False, {"Error": "Invalid filter operation, only 'in' or '=' is allowed"}

        return True, request_data['filters']['content']['value']


@rearrangement_ns.route('/<string:repertoire_id>')
@rearrangement_ns.param('repertoire_id', 'The repertoire identifier')
class RearrangementDownload(Resource):
    @rearrangement_ns.doc(description='Download rearrangement data for a specific repertoire')
    @rearrangement_ns.response(200, 'Success - Returns gzipped TSV file')
    @rearrangement_ns.response(404, 'File not found')
    @rearrangement_ns.response(503, 'Download limit exceeded')
    @rearrangement_ns.produces(['application/gzip'])
    def get(self, repertoire_id):
        in_limit, message = check_download_limit()
        if in_limit:
            filepath = RearrangementResource.get_rearrangements_file(self, repertoire_id)
            if filepath:
                update_bytes_transferred(os.path.getsize(filepath))
                study_id = os.path.split(filepath)[0]
                study_id = os.path.split(study_id)[1]
                transfer_file_name = study_id + '_' + os.path.basename(filepath)
                current_app.logger.info(f'sending {transfer_file_name}')

                return send_file(filepath, as_attachment=True, download_name=transfer_file_name, mimetype='application/gzip')
            else:
                return {"Error": "File not found"}, 404
        else:
            current_app.logger.info(message)
            return message, 503

