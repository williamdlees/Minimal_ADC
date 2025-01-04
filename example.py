import requests
import os


SERVER_URL = 'http://127.0.0.1:5000'


def download_study(study_name):
    repertoire_url = SERVER_URL + '/airr/v1/repertoire'
    request_body = {
        "filters": {
                "op": "=",
                "content":
                {
                    "field": "study_id",
                    "value": study_name
                },
        },
        "fields": ["repertoire_id", "subject.species.id", "sample.pcr_target.pcr_target_locus"]
    }

    try:
        response = requests.request(method='post', url=repertoire_url, json=request_body)
    except Exception as e:
        print(e)

    repertoires = response.json()['Repertoire']

    try:
        response = requests.request(method='get', url=repertoire_url + '/' + repertoires[0]['repertoire_id'])
    except Exception as e:
        print(e)

    if response.status_code == 200:
        url = SERVER_URL + '/airr/v1/rearrangement'
        if not os.path.exists(study_name):
            os.makedirs(study_name)
        for rep in repertoires:
            rep_id = rep['repertoire_id']
            request_body = {
                    "filters": {
                        "op": "=",
                        "content":
                            {
                                "field": "repertoire_id",
                                "value": rep_id
                            }
                    },
                    "format": "tsv"
                }
            response = requests.request(method='post', url=url, json=request_body)
            if response.status_code == 200:
                # Save the response content as a .gz file
                path_to_save = os.path.join(study_name, f'{rep_id}.tsv.gz')
                with open(path_to_save, 'wb') as file:
                    file.write(response.content)
                print(f"File saved as '{rep_id}.tsv.gz'")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('project_name', type=str, help="The name of your project")

    # args = parser.parse_args()

    download_study("PRJEB26509_IGH")
