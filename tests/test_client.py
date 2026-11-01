import httpx
import pytest
from test_loaders import ucdp_row

from ccrt import UCDPClient, UCDPError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("ccrt.client.time.sleep", lambda _: None)


def test_pagination_auth_filters_and_no_token_provenance():
    requests = []

    def handler(request):
        requests.append(request)
        page = int(request.url.params["page"])
        assert request.headers["x-ucdp-access-token"] == "private-key"
        assert request.url.params["Country"] == "645,678"
        assert request.url.params["StartDate"] == "2020-01-01"
        return httpx.Response(
            200,
            json={
                "TotalCount": 2,
                "TotalPages": 2,
                "NextPageUrl": "https://evil.example/steal",
                "Result": [ucdp_row(id=page + 1)],
            },
        )

    with UCDPClient("private-key", transport=httpx.MockTransport(handler)) as client:
        result = client.fetch(version="26.1", countries=[678, 645], start_date="2020-01-01", page_size=1)
    assert len(result) == 2
    assert len(requests) == 2
    assert [r.url.params["page"] for r in requests] == ["0", "1"]
    assert all(r.url.host == "ucdpapi.pcr.uu.se" for r in requests)
    assert "private-key" not in repr(result)


@pytest.mark.parametrize("status", [401, 403, 400, 302])
def test_nonretryable_errors_sanitized(status):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status, text="secret-token reflected")

    with UCDPClient("secret-token", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UCDPError) as error:
            client.fetch(version="26.1")
    assert count == 1
    assert "secret-token" not in str(error.value)


def test_transient_error_then_success():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"TotalCount": 0, "TotalPages": 0, "Result": []})

    with UCDPClient("key", transport=httpx.MockTransport(handler)) as client:
        assert len(client.fetch(version="26.1")) == 0
    assert len(calls) == 3


def test_bounded_network_retries():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("do not reflect key", request=request)

    with UCDPClient("key", retries=2, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UCDPError, match="connection failed"):
            client.fetch(version="26.1")
    assert count == 3


def test_long_retry_after_exits():
    with UCDPClient(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "86400"}))
    ) as client:
        with pytest.raises(UCDPError, match="longer retry"):
            client.fetch(version="26.1")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"TotalCount": "2", "TotalPages": 1, "Result": []},
        {"TotalCount": 1, "TotalPages": 1, "Result": []},
        {"TotalCount": 1, "TotalPages": 0, "Result": []},
        {"TotalCount": 0, "TotalPages": 1, "Result": [1]},
    ],
)
def test_invalid_response(payload):
    with UCDPClient(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(UCDPError):
            client.fetch(version="26.1")


def test_invalid_json():
    with UCDPClient(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>"))
    ) as client:
        with pytest.raises(UCDPError, match="invalid JSON"):
            client.fetch(version="26.1")


def test_repeated_page_is_not_silently_deduplicated():
    payload = {"TotalCount": 2, "TotalPages": 2, "Result": [ucdp_row()]}
    with UCDPClient(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(UCDPError, match="repeated a record"):
            client.fetch(version="26.1")


def test_page_limit_and_changed_counts():
    payload = {"TotalCount": 2, "TotalPages": 2, "Result": [ucdp_row()]}
    with UCDPClient(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(UCDPError, match="max_pages"):
            client.fetch(version="26.1", max_pages=1)

    def handler(request):
        if request.url.params["page"] == "1":
            return httpx.Response(200, json={**payload, "TotalCount": 3})
        return httpx.Response(200, json=payload)

    with UCDPClient("key", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UCDPError, match="count changed"):
            client.fetch(version="26.1")


def test_env_key_and_missing_key(monkeypatch):
    monkeypatch.delenv("UCDP_API_KEY", raising=False)
    with pytest.raises(UCDPError, match="Set UCDP_API_KEY"):
        UCDPClient()
    monkeypatch.setenv("UCDP_API_KEY", "example")
    with UCDPClient() as client:
        assert "example" not in repr(client)
