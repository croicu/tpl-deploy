from __future__ import annotations

import base64
import json
import pathlib
import urllib

import requests

from tests.shared.config import TestConfig
from tpl_deploy import protocols
from tpl_deploy.http_remote import HttpRemote, HttpTransport


class HttpBouncer(protocols.Transport):
    def __init__(self, name: str):
        self._name = name

    def __enter__(self) -> HttpBouncer:
        HttpRemote.set_transport(self)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        HttpRemote.set_transport(None)

    def get(self, *args, **kwargs) -> protocols.Response:
        raise AssertionError(f"Unexpected call to get(args={args}, kwargs={kwargs})")

    def get_if_modified(self, *args, **kwargs) -> protocols.Response:
        raise AssertionError(f"Unexpected call to get_if_modified(args={args}, kwargs={kwargs})")


_CHUNK_SIZE = 128


class HttpRecorder(protocols.Transport):
    def __init__(self, name: str):
        self._name = name
        self._messages: dict[str, tuple[int, str, bytes]] = {}

    def __enter__(self) -> HttpRecorder:

        HttpRemote.set_transport(self)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        HttpRemote.set_transport(None)

    def save(self):
        _recording_dir: pathlib.Path = TestConfig.data_dir() / "recordings"
        _recording_dir.mkdir(parents=True, exist_ok=True)
        _recording = _recording_dir / f"{self._name}.json"

        with open(_recording, "w", encoding="utf-8") as f:
            _sessions: dict[str, tuple[int, str, bytes]] = {}
            for _url, _message in self._messages.items():
                if _url not in _sessions:
                    if _message is None:
                        _sessions[_url] = ""
                    else:
                        _status_code = _message[0]
                        _etag = _message[1]

                        _payload = base64.b64encode(_message[2]).decode("ascii")
                        _chunks: list[str] = []
                        for i in range(0, len(_payload), _CHUNK_SIZE):
                            _chunks.append(_payload[i : i + _CHUNK_SIZE])

                        _sessions[_url] = [_status_code, _etag, _chunks]

            json.dump(_sessions, f, indent=2)

    def get(
        self,
        url: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:
        _response = self.http_transport.get(url, request_headers, inject_truststore)

        self._record_message(url, _response)

        return _response

    def get_if_modified(
        self,
        url: str,
        etag: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:
        _response = self.http_transport.get(url, request_headers, inject_truststore)

        self._record_message(url, _response)

        return _response

    # Private

    def _record_message(self, url: str, response: protocols.Response) -> None:
        _url_path = urllib.parse.urlparse(url)
        if _url_path.query != "":
            _url = _url_path.path + "?" + _url_path.query
        else:
            _url = _url_path.path

        self._messages[_url] = (response.status_code, response.etag, response.content)

    http_transport = HttpTransport()


class ResponsePlayer(protocols.Response):
    def __init__(self, response: tuple[int, str, bytes]):
        self._status_code = response[0]
        self._etag = response[1]
        self._content = response[2]

    @property
    def status_code(self):
        return self._status_code

    @property
    def reason(self):
        return "OK"

    @property
    def etag(self):
        return self._etag

    @property
    def content(self) -> bytes:
        return self._content

    def json(self):
        return json.loads(self._content.decode("utf-8"))

    def raise_for_status(self):
        if self._status_code >= 400:
            raise requests.exceptions.HTTPError(response=None)


class HttpPlayer(protocols.Transport):
    def __init__(self, name: str):
        self._name = name
        self._recording = None

    def __enter__(self) -> HttpPlayer:
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._messages: dict[str, tuple[int, str, bytes]] = {}
        self._open()

        HttpRemote.set_transport(self)

        return self

    def stop(self):
        HttpRemote.set_transport(None)

    def get(
        self,
        url: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:
        _url_path = urllib.parse.urlparse(url)
        if _url_path.query != "":
            _url = _url_path.path + "?" + _url_path.query
        else:
            _url = _url_path.path

        return ResponsePlayer(self._messages[_url])

    def get_if_modified(
        self,
        url: str,
        etag: str,
        request_headers: dict | None = None,
        inject_truststore: bool = True,
    ) -> protocols.Response:

        return self.get(url, request_headers, inject_truststore)

    def _open(self):
        _recording_dir: pathlib.Path = TestConfig.data_dir() / "recordings"
        _recording_dir.mkdir(parents=True, exist_ok=True)
        _recording = _recording_dir / f"{self._name}.json"

        with open(_recording, "r", encoding="utf-8") as f:
            for _url, _message in json.load(f).items():
                _status_code = _message[0]
                _etag = _message[1]
                _payload = base64.b64decode("".join(_message[2]))
                self._messages[_url] = (_status_code, _etag, _payload)
