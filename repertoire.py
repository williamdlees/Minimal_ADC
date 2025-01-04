from flask_restx import Namespace, Resource
from flask import request, current_app, Response
import os
import gzip
import json
import datetime
from json import JSONEncoder

repertoire_map = None
repertoire_ns = Namespace('repertoire', description='Repertoire operation repertoire_ns')
rearrangement_ns = Namespace('rearrangement', description='Repertoire operation rearrangement_ns')


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


def on_server_loads():
    if os.path.exists(current_app.config['USAGE_FILE_PATH']):
        with open(current_app.config['USAGE_FILE_PATH'], 'r') as file:
            existing_data = json.load(file, object_hook=decode_datetime)
            current_app.config['USAGE'] = existing_data


def update_file_limit():
    with open(current_app.config['USAGE_FILE_PATH'], 'w') as file:
        current_usage = current_app.config['USAGE']
        json.dump(current_usage, file, indent=4, cls=DateTimeEncoder)


def check_download_limit():
    if not os.path.exists(current_app.config['USAGE_FILE_PATH']):
        with open(current_app.config['USAGE_FILE_PATH'], 'w') as file:
            current_usage = current_app.config['USAGE']
            json.dump(current_usage, file, indent=4, cls=DateTimeEncoder)

    if current_app.config['FIRST_LOAD']:
        current_app.config['FIRST_LOAD'] = False
        on_server_loads()

    with open(current_app.config['USAGE_FILE_PATH'], 'r') as file:
        existing_data = json.load(file, object_hook=decode_datetime)
        current_usage = existing_data
        now = datetime.datetime.now()

        # Reset the usage if the week has passed
        if now - current_usage['start_date'] > datetime.timedelta(days=7):
            current_usage['start_date'] = now
            current_usage['bytes_transferred'] = 0

        # Check if the file size exceeds the limit
        if current_usage['bytes_transferred'] > current_app.config['WEEKLY_LIMIT']:
            return False, "Weekly download limit exceeded"

        # Update the usage
        return True, None

    return False, "error"


@repertoire_ns.route('/<string:repertoire_id>')
class RepertoireResource(Resource):
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
            repertoire_info = self.get_metadata(repertoire_info, {})

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
    def post(self):
        current_app.logger.info('Repertoire list was reached')
        if request.content_length > 0:
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
                return {"error": str(e)}, 400

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
        study_repertoires = None
        for metadata_path, repertoire_list in repertoire_map.items():
            if study_id is None or study_id in metadata_path:
                study_repertoires = self.get_all_repertoires_by_study_id(metadata_path)
        
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
    repertoire_map = {}
    studies_list = [study for study in os.listdir(studies_path)]
    for study in studies_list:
        study_path = os.path.join(studies_path, study)
        metadata_path = os.path.join(study_path, 'metadata.json')
        with open(metadata_path, 'r') as file:
            data = json.load(file)
            repertoire_list = []
            for repertoire in data["Repertoire"]:
                repertoire_list.append(repertoire["repertoire_id"])
            repertoire_map[metadata_path] = repertoire_list


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
    def post(self):
        in_limit, message = check_download_limit()
        current_usage = current_app.config['USAGE']
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
                        content, file_size, is_exist = self.get_rearrangements_files(response)
                        if is_exist:
                            current_app.logger.info(f'sending {response}.tsv.gz')
                            current_usage['bytes_transferred'] += file_size
                            update_file_limit()
                            response = Response(content, mimetype='application/gzip')
                            return response
                        else:
                            return {"Error": "File not found"}, 404
                        
                    else:
                        return {"Error": "Invalid request format"}, 400

            else:
                return {"Error": "Missing filters"}, 404
        else:
            current_app.logger.info(message)
            return {"Error":  message}, 403

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
                                        "count": int(file_repertoire["rearrangements"])
                                    }
                                )
        return facet_list

    def get_rearrangements_files(self, repertoire_id):
        if not isinstance(repertoire_id, list):
            repertoire_id = [repertoire_id]
        current_app.logger.info(f'Rearrangement files was reached with {repertoire_id}')
        for metadata_path, repertoire_list in repertoire_map.items():
            if repertoire_id[0] in repertoire_list:
                # Construct the file path for the .tsv.gz file
                filepath = metadata_path.replace('metadata.json', f"{repertoire_id[0]}.tsv.gz")
                print(filepath)
                if os.path.exists(filepath):
                    with gzip.open(filepath, 'rb') as f:
                        filesize = os.path.getsize(filepath)
                        content = f.read()
                        return content, filesize, True

                else:
                    current_app.logger.error(f"TSV file for {repertoire_id} not found.")
                    return {"error": "No TSV files found for the provided repertoire IDs"}, None, False

        return {"error": "No TSV files found for the provided repertoire IDs"}, None, False

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
