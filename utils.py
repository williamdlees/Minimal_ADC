import os
import shutil
import json

# Create 'log' and 'studies' directories if they don't exist and copy studies from a specified source to destination
def before_server_loads(config):
    if not os.path.exists(r'/log'):
        os.makedirs(r'/log')
    
    if not os.path.exists(r'/studies'):
        os.makedirs(r'/studies')
    #copy the studydies to madc file structure
    copy_folder_content(config["STUDIES_TO_COPY_PATH"], config["STUDIES_PATH"])


# Extracts repertoire, subject, and sample IDs from a JSON file
def get_repertoire_details(file_path):
    
    with open(file_path, 'r') as details:
        data = json.load(details)
        repertoire_id = data['repertoire_id']
        subject_id = data['subject_id']
        sample_id = data['sample_id']
    
    return repertoire_id, subject_id, sample_id

# Merges metadata from various sources into a single JSON file in the destination project
def merge_metadata(project_source, project_dest, tsv_map, pre_processed_map):
    project_metadata_path = os.path.join(os.path.join(project_source, r'project_metadata'), 'metadata.json')
    with open(project_metadata_path, 'r') as metadata:
        project_metadata = json.load(metadata)

        for file in tsv_map:
            repertoire_id, subject_id, sample_id = get_repertoire_details(file['repertoire_ids'])
            with open(file['annotation_metadata'], 'r') as annotation_metadata:
                annotation_metadata = json.load(annotation_metadata)
                update_annotated_metadata(project_metadata, repertoire_id, annotation_metadata)
        
        for file in pre_processed_map:
            repertoire_id, subject_id, sample_id = get_repertoire_details(file['repertoire_ids'])
            with open(file['pre_processed_metadata'], 'r') as pre_processed_metadata:
                pre_processed_metadata = json.load(pre_processed_metadata)
                update_pre_processed_metadata(project_metadata, repertoire_id, pre_processed_metadata)

        # Write the updated project_metadata to a new JSON file
        new_metadata_path = os.path.join(project_dest, 'metadata.json')
        with open(new_metadata_path, 'w') as new_metadata_file:
            json.dump(project_metadata, new_metadata_file, indent=4)

# Updates project metadata with annotated metadata for a specific repertoire
def update_annotated_metadata(project_metadata, repertoire_id, annotation_metadata):
    new_data = annotation_metadata['sample']['data_processing']
    for repertoire in project_metadata['Repertoire']:
        if repertoire['repertoire_id'] == repertoire_id:
            original_data = repertoire['data_processing'][0]
            repertoire['data_processing'][0] = merge_json_data_recursive(original_data, new_data)

# Updates project metadata with pre-processed metadata for a specific repertoire
def update_pre_processed_metadata(project_metadata, repertoire_id, pre_processed_metadata):
    new_data = pre_processed_metadata['sample']['data_processing']
    for repertoire in project_metadata['Repertoire']:
        if repertoire['repertoire_id'] == repertoire_id:
            original_data = repertoire['data_processing'][0]
            repertoire['data_processing'][0] = merge_json_data_recursive(original_data, new_data)


def merge_json_data_recursive(original_data, new_data):
    """
    Recursively merges new_data into original_data. If a key in new_data already exists in original_data
    and both values are dictionaries, it merges them recursively. If both are lists, it appends the items
    from the new list to the old list. Otherwise, the value in original_data is updated with the value from new_data.
"""
    for key, value in new_data.items():
        if key in original_data:
            if isinstance(original_data[key], dict) and isinstance(value, dict):
                merge_json_data_recursive(original_data[key], value)
            elif isinstance(original_data[key], list) and isinstance(value, list):
                original_data[key].extend(value)
            else:
                original_data[key] = value
        else:
            original_data[key] = value

    return original_data


# Copies content from a source directory to a destination directory and merges metadata
def copy_folder_content(src, dst):
    if not os.path.exists(src):
        raise ValueError(f"Source folder {src} does not exist")

    # Create the destination directory if it does not exist
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    for project in os.listdir(src):
        project_path = os.path.join(src, project)
        tsv_files_paths, pre_processed_files = find_project_tsv_files(project_path)

        project_dest = os.path.join(dst, project)
        if not os.path.exists(project_dest):
            os.makedirs(project_dest)

        # Copy each file and subfolder from src to dst
        for tsv_file_path in tsv_files_paths:
            dest = os.path.join(project_dest, tsv_file_path['file_name'])
            if not os.path.exists(dest):
                shutil.copy2(tsv_file_path['file_path'], dest) # For files

        merge_metadata(project_path, project_dest, tsv_files_paths, pre_processed_files)


# Finds TSV files and pre-processed files within a project directory
def find_project_tsv_files(project_path):
    pre_processed_folders = []
    try:
        runs_folder = os.path.join(project_path, 'runs')
        folders = os.listdir(runs_folder)
        for folder in folders:
            folder_path = os.path.join(runs_folder, folder)
            annotated_folder_path = os.path.join(folder_path, 'annotated')
            annotated_folders = os.listdir(annotated_folder_path)
            pre_processed_folder_path = os.path.join(folder_path, 'pre_processed')
            if os.path.exists(pre_processed_folder_path):
                pre_processed_folders = os.listdir(pre_processed_folder_path)
            
            tsv_files = start_scan(annotated_folder_path,annotated_folders , False)
            pre_processed_files = start_scan(pre_processed_folder_path, pre_processed_folders , True)

    except Exception as e:
        print(e)

    return tsv_files, pre_processed_files

# Initiates scanning of folders for TSV and metadata files
def start_scan(folder_path,folders, pre_processed):
    files = []
    for subject in folders:
        subject_path = os.path.join(folder_path, subject)
        res = scan_subject_folder(subject_path, pre_processed)
        for file in res:
            files.append(file)
    
    return files

# Scans a subject folder for TSV and metadata files
def scan_subject_folder(subject_path, pre_processed):
    tsv_files = []
    samples = os.listdir(subject_path)
    for sample in samples:
        sample_path = os.path.join(subject_path, sample)
        files = scan_run_folder(sample_path, pre_processed)
        for file in files:
            tsv_files.append(file)
    
    return tsv_files

# Scans a run folder for TSV and metadata files
def scan_run_folder(sample_path, pre_processed):
    tsv_files = []
    runs = os.listdir(sample_path)
    for run in runs:
        run_path = os.path.join(sample_path, run)
        run_results = os.listdir(run_path)
        for result in run_results:
            result_path = os.path.join(run_path, result)
            if not pre_processed:
                file = find_tsv_and_metadata_for_annotated(result_path)
            else:
                file = find_metadata_for_pre_processed(result_path)

            if file != None:
                tsv_files.append(file[0])
    
    return tsv_files

# Finds metadata for pre-processed results
def find_metadata_for_pre_processed(result_path):
    res_list = []
    res = {
        'repertoire_ids': None,
        'pre_processed_metadata': None
    }
    result_folders = os.listdir(result_path)
    for folder in result_folders:
        folder_path = os.path.join(result_path, folder)
        folder_files = os.listdir(folder_path)
        
        if 'meta_data' in folder:
            if 'pre_processed_metadata.json' in folder_files:
                res['pre_processed_metadata'] = os.path.join(folder_path, 'pre_processed_metadata.json')
            
            if 'repertoire_id.json' in folder_files:
                res['repertoire_ids'] = os.path.join(folder_path, 'repertoire_id.json')

    check_result_fileds(res, result_path)
    if all(value is not None for value in res.values()):
        res_list.append(res)
        return res_list
    
    return None     
                

# Finds TSV files and their corresponding metadata for annotated results
def find_tsv_and_metadata_for_annotated(result_path):
    res_list = []
    res = {
            'file_path': None,
            'file_name': None,
            'repertoire_ids': None,
            'annotation_metadata': None
        }
    
    result_folders = os.listdir(result_path)
    for folder in result_folders:
        folder_path = os.path.join(result_path, folder)
        folder_files = os.listdir(folder_path)
        for file in folder_files:
            if 'Finale' in file:
                res['file_path'] = os.path.join(folder_path, file)
                res['file_name'] = file
            
            if file == 'repertoire_id.json':
                res['repertoire_ids'] = os.path.join(folder_path, file)
        
        if 'meta_data' in folder:
            if 'annotation_metadata.json' in folder_files:
                res['annotation_metadata'] = os.path.join(folder_path, 'annotation_metadata.json')

    check_result_fileds(res, result_path)
    if all(value is not None for value in res.values()):
        res_list.append(res)
        return res_list
    
    return None 

# Checks if all required fields in a result are present
def check_result_fileds(result, folder):
    for key, value in result.items():
        if value == None:
            print(f"{key} was not found in the {folder}")