import errno
from flask import request
from flask_restful import Resource

from base64 import b64encode, b64decode

import json
import os
import shutil
import subprocess

TEMP_DIR = './compilations/'
OUT_DIR = './output/'
COMPILER = 'gcc'
SED = 'sed'
OUTPUT_FILENAME = 'output.exe' if os.name == 'nt' else 'output'

def create_file_with_path(path_to_file):
    if not os.path.exists(os.path.dirname(path_to_file)):
        try:
            os.makedirs(os.path.dirname(path_to_file))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

def extract_headers(data):
    return data.split('\n')

def encode_bytes(data: bytes):
    return b64encode(data).decode()

def decode_bytes(data: str):
    return b64decode(data.encode())

def encode_file(path):
    with open(path, 'rb') as f:
        return encode_bytes(f.read())

def clear_directory(directory):
    contents = [os.path.join(directory, i) for i in os.listdir(directory)]
    [os.remove(i) if os.path.isfile(i) or os.path.islink(i) else shutil.rmtree(i) for i in contents]

def get_dependencies(req):
    all_headers = []
    json_content = req.get_json()
    files_list = json_content['files']
    for file in files_list:
        server_path = TEMP_DIR + file['path']
        create_file_with_path(server_path)
        with open(TEMP_DIR + file['path'], 'wb+') as f:
            file_data = file['data']
            f.write(decode_bytes(file_data))
        try:
            dependencies = subprocess.check_output(
                [SED, r""'s/#include "\(.*\)".*/\\1/;tx;d;:x'"", server_path],
                shell=True
            ).strip().decode()
            if len(dependencies) > 0:
                additional_headers = [
                    os.path.join(os.path.dirname(file['path']), path) for path in extract_headers(dependencies)
                ]
                all_headers.extend(additional_headers)
        except subprocess.CalledProcessError as err:
            print(err.output)
    return all_headers

def compile(req):
    paths = [TEMP_DIR + file['path'] for file in req.get_json()['files']]
    output_args = ['-o', OUT_DIR + OUTPUT_FILENAME]
    compilation_output = None
    try:
        compilation_output = subprocess.check_output(
            [COMPILER] + paths + [arg for arg in req.get_json()['options']] + output_args,
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        return json.dumps({
            'returnCode': e.returncode,
            'errorMessage': e.output.decode()
        })

    compilation_messages = compilation_output.decode().split('\n')
    return json.dumps( {
            'outputFile': encode_file(OUT_DIR + OUTPUT_FILENAME),
            'compilationMessages': compilation_messages
        }
    )

class Compilations(Resource):
    endpoint = '/compilations'
    def post(self):
        clear_directory(TEMP_DIR)
        all_headers = get_dependencies(request)
        additional_headers = [header for header in all_headers if not os.path.isfile(TEMP_DIR + header)]

        if additional_headers:
            return json.dumps({
                'requiredHeaders': [encode_bytes(dependency.encode()) for dependency in additional_headers ]
            })
        else:
            return compile(request)