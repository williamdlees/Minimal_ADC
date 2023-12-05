import os
import shutil


def before_server_loads(config):
    #copy the studydies to madc file structure
    copy_folder_content(config["STUDIES_TO_COPY_PATH"], config["STUDIES_PATH"])


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
            dest = os.path.join(project_dest, tsv_file_path[1])
            if not os.path.exists(dest):
                shutil.copy2(tsv_file_path[0], dest) # For files

def find_project_tsv_files(project_path):
    tsv_files = []
    try:
        runs_folder = os.path.join(project_path, 'runs')
        folders = os.listdir(runs_folder)
        for folder in folders:
            folder_path = os.path.join(runs_folder, folder)
            annotated_folder_path = os.path.join(folder_path, 'annotated')
            annotated_folders = os.listdir(annotated_folder_path)
            
            for subject in annotated_folders:
                subject_path = os.path.join(annotated_folder_path, subject)
                files = scan_subject_folder(subject_path)
                for file in files:
                    tsv_files.append(file)
    
    except Exception as e:
        print(e)

    return tsv_files


def scan_subject_folder(subject_path):
    tsv_files = []
    samples = os.listdir(subject_path)
    for sample in samples:
        sample_path = os.path.join(subject_path, sample)
        files = scan_run_folder(sample_path)
        for file in files:
            tsv_files.append(file)
    
    return tsv_files

def scan_run_folder(sample_path):
    tsv_files = []
    runs = os.listdir(sample_path)
    for run in runs:
        run_path = os.path.join(sample_path, run)
        run_readsets = os.listdir(run_path)
        for readset in run_readsets:
            readset_path = os.path.join(run_path, readset)
            file = find_tsv(readset_path)
            if file != None:
                tsv_files.append(file)
    
    return tsv_files


def find_tsv(readset_path):
    tsv_folder = os.path.join(readset_path, 'rearrangements')
    tsv_folder_content = os.listdir(tsv_folder)
    for file in tsv_folder_content:
        if 'Third' in file:
            return [os.path.join(tsv_folder, file), file]
    
    return print(f"{tsv_folder} doesnt has the right tsv file")

