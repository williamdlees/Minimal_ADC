import os
import shutil
import json

def before_server_loads(config):
    if not os.path.exists('log'):
        os.makedirs('log')
    
    if not os.path.exists('studies'):
        os.makedirs('studies')
    #copy the studydies to madc file structure
    copy_folder_content(config["STUDIES_TO_COPY_PATH"], config["STUDIES_PATH"])


def merge_metadata(project_source, project_dest, map):
    project_metadata_path = os.path.join(os.path.join(project_source, r'project_metadata'), 'metadata.json')
    with open(project_metadata_path, 'r') as metadata:
        project_metadata = json.load(metadata)

        for file in map:
            repertoire_id, subject_id, sample_id = get_repertoire_details(file['repertoire_ids'])
            with open(file['annotation_metadata'], 'r') as annotation_metadata:
                annotation_metadata = json.load(annotation_metadata)
                update_metadata(project_metadata, repertoire_id, annotation_metadata)

            # Write the updated project_metadata to a new JSON file
        new_metadata_path = os.path.join(project_dest, 'metadata.json')
        with open(new_metadata_path, 'w') as new_metadata_file:
            json.dump(project_metadata, new_metadata_file, indent=4)




def update_metadata(project_metadata, repertoire_id, annotation_metadata):
    new_data = annotation_metadata['sample']['data_processing']
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

def get_repertoire_details(file_path):
    with open(file_path, 'r') as details:
        data = json.load(details)
        repertoire_id = data['repertoire_id']
        subject_id = data['subject_id']
        sample_id = data['sample_id']
    
    return repertoire_id, subject_id, sample_id


def copy_folder_content(src, dst):
    if not os.path.exists(src):
        raise ValueError(f"Source folder {src} does not exist")

    # Create the destination directory if it does not exist
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    for project in os.listdir(src):
        project_path = os.path.join(src, project)
        tsv_files_paths = find_project_tsv_files(project_path)

        project_dest = os.path.join(dst, project)
        if not os.path.exists(project_dest):
            os.makedirs(project_dest)

        # Copy each file and subfolder from src to dst
        for tsv_file_path in tsv_files_paths:
            dest = os.path.join(project_dest, tsv_file_path['file_name'])
            if not os.path.exists(dest):
                shutil.copy2(tsv_file_path['file_path'], dest) # For files

        merge_metadata(project_path, project_dest, tsv_files_paths)

def find_project_tsv_files(project_path):
    tsv_files = []
    pre_processed = False
    try:
        runs_folder = os.path.join(project_path, 'runs')
        folders = os.listdir(runs_folder)
        for folder in folders:
            folder_path = os.path.join(runs_folder, folder)
            annotated_folder_path = os.path.join(folder_path, 'annotated')
            annotated_folders = os.listdir(annotated_folder_path)
            if os.path.exists(os.path.join(folder_path, 'pre_processed')):
                pre_processed = True
            
            for subject in annotated_folders:
                subject_path = os.path.join(annotated_folder_path, subject)
                files = scan_subject_folder(subject_path, False)
                # if pre_processed:
                #     pre_processed_metadata = scan_subject_folder(subject_path, True)

                for file in files:
                    tsv_files.append(file)
    
    except Exception as e:
        print(e)

    return tsv_files


def scan_subject_folder(subject_path, pre_processed):
    tsv_files = []
    samples = os.listdir(subject_path)
    for sample in samples:
        sample_path = os.path.join(subject_path, sample)
        files = scan_run_folder(sample_path, pre_processed)
        for file in files:
            tsv_files.append(file)
    
    return tsv_files

def scan_run_folder(sample_path, pre_processed):
    tsv_files = []
    runs = os.listdir(sample_path)
    for run in runs:
        run_path = os.path.join(sample_path, run)
        run_results = os.listdir(run_path)
        for result in run_results:
            result_path = os.path.join(run_path, result)
            file = find_tsv_and_metadata(result_path, pre_processed)
            if file != None:
                tsv_files.append(file[0])
    
    return tsv_files


def find_tsv_and_metadata(result_path, pre_processed):
    res_list = []
    res = {}
    metadata_path = None
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
                metadata_path = os.path.join(folder_path, 'annotation_metadata.json')
                

    if len(res) > 0 :
        if metadata_path != None:
            res['annotation_metadata'] = metadata_path
            res_list.append(res)
            return res_list
        else:
            print(f"{result_path} has no metadata file")

    else:
        print(f"{result_path} doesnt has the right tsv file")
    
    return None 

