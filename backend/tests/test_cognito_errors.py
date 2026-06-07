from botocore.exceptions import ClientError

from app.core.exceptions import AuthError, ConflictError, ExternalServiceError
from app.services.cognito import _map_client_error


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "msg"}}, "Operation")


def test_username_exists_maps_to_conflict() -> None:
    assert isinstance(_map_client_error(_client_error("UsernameExistsException")), ConflictError)


def test_not_authorized_maps_to_auth_error() -> None:
    assert isinstance(_map_client_error(_client_error("NotAuthorizedException")), AuthError)


def test_unknown_code_maps_to_external_service_error() -> None:
    assert isinstance(_map_client_error(_client_error("SomethingElse")), ExternalServiceError)
