import jsonschema
import requests
from requests.auth import HTTPBasicAuth
from copy import deepcopy


_HTTP_METHODS = ['Get', 'Put', 'Post']
_HTTP_METHODS_ENUMS = deepcopy(_HTTP_METHODS) + [m.lower() for m in _HTTP_METHODS] + [m.upper() for m in _HTTP_METHODS]

_AUTH_METHODS = ['Basic', 'Digest']
_AUTH_METHODS_ENUMS = deepcopy(_AUTH_METHODS) + [m.lower() for m in _AUTH_METHODS] + [m.upper() for m in _AUTH_METHODS]


http_send_schema = {
    'type': 'object',
    'properties': {
        'baseUrl': {'type': 'string'},
        'project': {'type': 'string'},
        'subject': {'type': 'string'},
        'session': {'type': 'string'},
        'containerType': {'enum': ['scans', 'reconstructions', 'assessors']},
        'container': {'type': 'string'},
        'resource': {'type': 'string'},
        'xsiType': {'type': 'string'},
        'file': {'type': 'string'},
        'upsert': {'type': 'boolean'},
        'auth': {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'}
            },
            'additionalProperties': False,
            'required': ['username', 'password']
        },
        'disableSSLVerification': {'type': 'boolean'},
    },
    'additionalProperties': False,
    'required': ['baseUrl', 'project', 'subject', 'session', 'containerType', 'container', 'xsiType', 'file', 'auth']
}

http_receive_schema = {
    'oneOf': [{
        'type': 'object',
        'properties': {
            'baseUrl': {'type': 'string'},
            'project': {'type': 'string'},
            'subject': {'type': 'string'},
            'session': {'type': 'string'},
            'containerType': {'enum': ['scans', 'reconstructions', 'assessors']},
            'container': {'type': 'string'},
            'resource': {'type': 'string'},
            'file': {'type': 'string'},
            'auth': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'}
                },
                'additionalProperties': False,
                'required': ['username', 'password']
            },
            'disableSSLVerification': {'type': 'boolean'},
        },
        'additionalProperties': False,
        'required': [
            'baseUrl', 'project', 'subject', 'session', 'containerType', 'container', 'resource', 'file', 'auth'
        ]
    }, {
        'type': 'object',
        'properties': {
            'baseUrl': {'type': 'string'},
            'project': {'type': 'string'},
            'subject': {'type': 'string'},
            'session': {'type': 'string'},
            'resource': {'type': 'string'},
            'file': {'type': 'string'},
            'auth': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'}
                },
                'additionalProperties': False,
                'required': ['username', 'password']
            },
            'disableSSLVerification': {'type': 'boolean'},
        },
        'additionalProperties': False,
        'required': ['baseUrl', 'project', 'subject', 'session', 'resource', 'file', 'auth']
    }]
}


def _auth_method_obj(access):
    if not access.get('auth'):
        return None

    auth = access['auth']

    return HTTPBasicAuth(
        auth['username'],
        auth['password']
    )


class Http:
    @staticmethod
    def receive(access, internal):
        auth_method_obj = _auth_method_obj(access)

        verify = True
        if access.get('disableSSLVerification'):
            verify = False

        base_url = access['baseUrl'].rstrip('/')
        project = access['project']
        subject = access['subject']
        session = access['session']
        container_type = access.get('containerType')
        container = access.get('container')
        resource = access['resource']
        file = access['file']

        url = '{}/REST/projects/{}/subjects/{}/experiments/{}/resources/{}/files/{}'.format(
            base_url, project, subject, session, resource, file
        )

        if container_type:
            url = '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}/resources/{}/files/{}'.format(
                base_url, project, subject, session, container_type, container, resource, file
            )

        r = requests.get(
            url,
            auth=auth_method_obj,
            verify=verify,
            stream=True
        )
        r.raise_for_status()

        with open(internal['path'], 'wb') as f:
            for chunk in r.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)
        r.raise_for_status()

        cookies = r.cookies

        r = requests.delete(
            '{}/data/JSESSION'.format(base_url),
            cookies=cookies,
            verify=verify
        )
        r.raise_for_status()

    @staticmethod
    def receive_validate(access):
        jsonschema.validate(access, http_receive_schema)

    @staticmethod
    def send(access, internal):
        auth_method_obj = _auth_method_obj(access)

        verify = True
        if access.get('disableSSLVerification'):
            verify = False

        base_url = access['baseUrl'].rstrip('/')
        project = access['project']
        subject = access['subject']
        session = access['session']
        container_type = access['containerType']
        container = access['container']
        resource = access.get('resource', 'OTHER')
        xsi_type = access['xsiType']
        file = access['file']
        upsert = access.get('upsert')

        r = requests.get(
            '{}/REST/projects/{}/subjects/{}/experiments/{}/{}?format=json'.format(
                base_url, project, subject, session, container_type
            ),
            auth=auth_method_obj,
            verify=verify
        )
        r.raise_for_status()
        existing_containers = r.json()['ResultSet']['Result']
        cookies = r.cookies

        container_exists = False
        for ec in existing_containers:
            if ec['ID'] == container:
                container_exists = True
                break

        if container_exists:
            if not upsert:
                raise Exception('Container {} already exists and upsert is not set.'.format(container))

            r = requests.get(
                '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}/resources?format=json'.format(
                    base_url, project, subject, session, container_type, container
                ),
                cookies=cookies,
                verify=verify
            )
            r.raise_for_status()
            existing_resources = r.json()['ResultSet']['Result']

            resource_exists = False
            for er in existing_resources:
                if er['label'] == resource:
                    resource_exists = True
                    break

            if resource_exists:
                r = requests.get(
                    '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}/resources/{}/files?format=json'.format(
                        base_url, project, subject, session, container_type, container, resource
                    ),
                    cookies=cookies,
                    verify=verify
                )
                r.raise_for_status()
                existing_files = r.json()['ResultSet']['Result']

                file_exists = False
                for ef in existing_files:
                    if ef['Name'] == file:
                        file_exists = True
                        break

                if file_exists:
                    # delete file
                    r = requests.delete(
                        '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}/resources/{}/files/{}'.format(
                            base_url, project, subject, session, container_type, container, resource, file
                        ),
                        cookies=cookies,
                        verify=verify
                    )
                    r.raise_for_status()

            # delete container
            r = requests.delete(
                '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}'.format(
                    base_url, project, subject, session, container_type, container
                ),
                cookies=cookies,
                verify=verify
            )
            r.raise_for_status()

        # create container
        r = requests.put(
            '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}?xsiType={}'.format(
                base_url, project, subject, session, container_type, container, xsi_type
            ),
            cookies=cookies,
            verify=verify
        )
        r.raise_for_status()

        # create file
        with open(internal['path'], 'rb') as f:
            r = requests.put(
                '{}/REST/projects/{}/subjects/{}/experiments/{}/{}/{}/resources/{}/files/{}?inbody=true'.format(
                    base_url, project, subject, session, container_type, container, resource, file
                ),
                data=f,
                cookies=cookies,
                verify=verify
            )
            r.raise_for_status()

        # delete session
        r = requests.delete(
            '{}/data/JSESSION'.format(
                base_url
            ),
            cookies=cookies,
            verify=verify
        )
        r.raise_for_status()

    @staticmethod
    def send_validate(access):
        jsonschema.validate(access, http_send_schema)
