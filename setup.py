
from app import rest_api

import endpoint

def register_resource(resource):
    rest_api.add_resource(resource, resource.endpoint)

register_resource(endpoint.Compilations)
