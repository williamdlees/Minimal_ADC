from flask_restx import Namespace, Resource
from flask import request, current_app, send_file, make_response, Response
import os
import gzip
import shutil
import json


repertoire_map = None
repertoire_ns = Namespace('repertoire', description='Repertoire operation repertoire_ns')
rearrangement_ns = Namespace('rearrangement', description='Repertoire operation rearrangement_ns')



@repertoire_ns.route('<string:repertoire_id>')
class RepertoireResource(Resource):
    def get(self, repertoire_id):
        current_app.logger.info(f'Repertoire information for {repertoire_id} was reached')
        repertoire_info = None
        metadata_path = self.find_repertoire_path_by_id(repertoire_id)
        if metadata_path is not None:
            repertoire_info = self.get_repertoire_information(metadata_path, repertoire_id)
            if not repertoire_info:
                current_app.logger.error(f'error with finding reperoire information in {metadata_path}')
        else:
            current_app.logger.info(f'{repertoire_id} not found')
            repertoire_info = "Not Found"

        return {"Info" : current_app.config["API_INFORMATION"] ,
                "Repertoire": repertoire_info}
    
    #finding the repertoire metadata path by the repertoire id
    def find_repertoire_path_by_id(self, repertoire_id):
        path = None
        for metadata_path, repertoire_list in repertoire_map.items():
            for repertoire in repertoire_list:
                if repertoire == repertoire_id:
                    path = metadata_path
                    break
        
        return path
        
    
    #return the repertoire information by the metadata path
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
            return {"Info": current_app.config["API_INFORMATION"],
                    "Repertoire": study_repertoires}

        all_repertoires = self.get_all_repertoires()
        return {"Info": current_app.config["API_INFORMATION"],
                "Repertoire": all_repertoires}


    def validate_repertoire_request(self, request_data):
        expected_keys = ['filters']
        for key in request_data:
            if key not in expected_keys:
                return False, {"Error": f"Unexpected field '{key}' in request"}
            
        if 'filters' not in request_data:
            return False, {"Error": "Missing 'filters' in request"}

        filters = request_data['filters']
        if 'content' not in filters or 'op' not in filters:
            return False, {"Error": "Missing 'content' or 'op' in filters"}

        expected_filters = ['content','op']
        for filter in expected_filters:
            if filter not in expected_filters:
                return False, {"Error": f"Unexpected filters '{filter}' in request"}
            
        filter_content = filters['content']
        filter_op = filters['op']

        if 'field' not in filter_content:
            return False, {"Error": "Missing 'field' in filter content"}
        
        if 'value' not in filter_content:
            return False, {"Error": "Missing 'value' in filter content"}

        expected_content = ['field','value']
        for content in expected_content:
            if content not in expected_content:
                return False, {"Error": f"Unexpected content '{content}' in request"}
            
        if filter_content['field'] != 'study.study_id':
            return False, {"Error": "Invalid filter field, only 'study.study_id' is allowed"}

        if filter_op != '=':
            return False, {"Error": "Invalid filter operation, only '=' is allowed"}

        return True, filter_content['value']

    #finding the right study and returning its repertoires
    def filter_repertoires_by_study(self, study_id):
        study_repertoires = None
        for metadata_path, repertoire_list in repertoire_map.items():
            if study_id in metadata_path:
                study_repertoires = self.get_all_repertoires_by_study_id(metadata_path)
        
        return study_repertoires

    #returning all study's repertoires that available in the server
    def get_all_repertoires_by_study_id(self, metadata_path):
        study_repertoires = []
        with open(metadata_path, 'r') as metadata_file:
            data = json.load(metadata_file)
            for repertoire in data["Repertoire"]:
                study_repertoires.append(repertoire)
        
        return study_repertoires


    #returning all repertoires that available in the server
    def get_all_repertoires(self):
        all_repertoires = []
        for metadata_path, repertoire_list in repertoire_map.items():
            study_repertoires = self.get_all_repertoires_by_study_id(metadata_path)
            for repertoire in study_repertoires:
                all_repertoires.append(repertoire)

        return all_repertoires
    


#creating a map of metadata-path(key) and list of the repertoires in that(value)
def create_repertoire_map(studies_path):
    global repertoire_map
    print(f'Creating repertoire map')
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



@rearrangement_ns.route('')
class RearrangementResource(Resource):
    def post(self):
        if request.content_length > 0:
            request_data = request.get_json()
            valid, response = self.validate_request(request_data)
            
            if not valid:
                return response, 400
            
            else:
                if 'facets' in request_data:
                    rearrangement_response = self.get_rearrangements_count(response)
                    return {"Info": current_app.config["API_INFORMATION"],"Facet": rearrangement_response}
                
                elif 'format' in request_data:
                    content, is_exist  = self.get_rearrangements_files(response)
                    if is_exist:
                        current_app.logger.info(f'sending {response}.tsv')
                        return Response(content, mimetype='text/tab-separated-values')
                    else:
                        return {"Error": "File not found"}, 404
                
                else:
                    return {"Error": "Invalid request format"}, 400
                
        else:
            return {"Error": "Missing filters"}, 404

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
                                    {"repertoire_id" : repertoire,
                                     "count" : int(file_repertoire["rearrangements"])
                                    }
                                )
        return facet_list



    def get_rearrangements_files(self, repertoire_id):
        current_app.logger.info(f'Rearrangement files was reached with {repertoire_id}')
        #for repertoire_id in repertoire_ids:
        for metadata_path, repertoire_list in repertoire_map.items():
            if repertoire_id in repertoire_list:
                # Construct the file path for the .tsv.gz file
                gz_filepath  = metadata_path.replace('metadata.json', f"{repertoire_id}.tsv.gz")
                if os.path.exists(gz_filepath ):
                    with gzip.open(gz_filepath, 'rt') as f:  # 'rt' mode for reading as text
                        content = f.read()
                        return content, True

                else:
                    current_app.logger.error(f"TSV file for {repertoire_id} not found.")
                    return {"error": "No TSV files found for the provided repertoire IDs"}, False
                
        return {"error": "No TSV files found for the provided repertoire IDs"}, False


    def validate_request(self, request_data):
        facets_in_request = True
        format_in_request = True

        expected_keys = ['filters', 'facets','format']
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
        expected_filters = ['content','op']
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
        expected_content = ['field','value']
        for content in expected_content:
            if content not in expected_content:
                return False, {"Error": f"Unexpected content '{content}' in request"}
            
        if filter_content['field'] != 'repertoire_id':
            return False, {"Error": "Invalid filter field, only 'repertoire_id' is allowed"}

        # Validate filter operation
        if filter_op != 'in':
            return False, {"Error": "Invalid filter operation, only 'in' is allowed"}

        return True, request_data['filters']['content']['value']

