import pytest
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app


@pytest.fixture
async def client():
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    app.state.http_client = mock_http

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client, mock_http


@pytest.fixture
def headers():
    return {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


@patch("app.SERVER_API_TOKEN", "test-token")
@patch("app.MXROUTE_SERVER", "mx.example.com")
@patch("app.MXROUTE_USERNAME", "user")
@patch("app.MXROUTE_API_KEY", "key")
class TestApp:
    @pytest.mark.anyio
    async def test_auth_missing_token(self, client):
        test_client, _ = client
        res = await test_client.get("/")
        assert res.status_code == 401
        assert "Missing or invalid Authorization header" in res.json()["error"]

    @pytest.mark.anyio
    async def test_auth_invalid_token(self, client):
        test_client, _ = client
        res = await test_client.get("/", headers={"Authorization": "Bearer wrong"})
        assert res.status_code == 401
        assert "Invalid token" in res.json()["error"]

    @pytest.mark.anyio
    async def test_options_no_auth(self, client):
        test_client, _ = client
        res = await test_client.options(
            "/",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200

    @pytest.mark.anyio
    async def test_status_success(self, client, headers):
        test_client, _ = client
        res = await test_client.get("/", headers=headers)
        assert res.status_code == 200
        assert b"Bitwarden Mxroute plugin is running healthy" in res.content

    @pytest.mark.anyio
    @patch("app.get_current_datetime")
    async def test_add_success_default(self, mock_now, client, headers):
        test_client, mock_http = client
        mock_now.return_value = datetime(2026, 2, 8)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_http.post.return_value = mock_response

        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=example.com"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)

        assert res.status_code == 200
        assert res.json()["data"]["email"] == "com-example-0262@example.com"

        mock_http.post.assert_called_once()
        args, kwargs = mock_http.post.call_args
        assert args[0] == "https://api.mxroute.com/domains/example.com/forwarders"
        assert kwargs["json"]["alias"] == "com-example-0262"
        assert kwargs["json"]["destinations"] == ["dest@example.com"]

    @pytest.mark.anyio
    @patch("app.secrets.token_hex")
    @patch("app.coolname.generate")
    async def test_add_success_template(
        self, mock_coolname, mock_hex, client, headers
    ):
        test_client, mock_http = client
        mock_coolname.return_value = ["slug"]
        mock_hex.return_value = "abcdef"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_http.post.return_value = mock_response

        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=example.com,template=<slug>-<hex>,slug_length=1"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)

        assert res.status_code == 200
        assert res.json()["data"]["email"] == "slug_abcdef@example.com"

    @pytest.mark.anyio
    async def test_add_missing_options(self, client, headers):
        test_client, _ = client
        data = {"domain": "prefix=foo"}
        res = await test_client.post("/add/dummy", headers=headers, json=data)
        assert res.status_code == 412
        assert "options are required" in res.json()["error"]

    @pytest.mark.anyio
    async def test_add_missing_target(self, client, headers):
        test_client, _ = client
        data = {"domain": "domain=example.com,destination=dest@example.com"}
        res = await test_client.post("/add/dummy", headers=headers, json=data)
        assert res.status_code == 412
        assert "options are required" in res.json()["error"]

    @pytest.mark.anyio
    async def test_add_invalid_target(self, client, headers):
        test_client, _ = client
        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=invalid"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)
        assert res.status_code == 412
        assert "must be a valid domain" in res.json()["error"]

    @pytest.mark.anyio
    async def test_add_invalid_template(self, client, headers):
        test_client, _ = client
        data = {"domain": "domain=d,destination=d,target=example.com,template=<bad>"}
        res = await test_client.post("/add/dummy", headers=headers, json=data)
        assert res.status_code == 412
        assert "Template part 'bad' is not allowed" in res.json()["error"]

    @pytest.mark.anyio
    @patch("app.get_current_datetime")
    async def test_add_multilevel_tld_target(self, mock_now, client, headers):
        test_client, mock_http = client
        mock_now.return_value = datetime(2026, 2, 1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_http.post.return_value = mock_response

        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=blog.example.co.uk"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)

        assert res.status_code == 200
        assert res.json()["data"]["email"] == "uk-example-0261@example.com"

    @pytest.mark.anyio
    @patch("app.get_current_datetime")
    async def test_add_truncates_host_to_8_chars(self, mock_now, client, headers):
        test_client, mock_http = client
        mock_now.return_value = datetime(2026, 2, 1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_http.post.return_value = mock_response

        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=verylonghostname.com"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)

        assert res.status_code == 200
        assert res.json()["data"]["email"] == "com-verylong-0261@example.com"

    @pytest.mark.anyio
    @patch("app.get_current_datetime")
    async def test_add_applies_prefix_and_suffix(self, mock_now, client, headers):
        test_client, mock_http = client
        mock_now.return_value = datetime(2026, 2, 1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_http.post.return_value = mock_response

        data = {
            "domain": "domain=example.com,destination=dest@example.com,target=example.com,prefix=foo,suffix=bar,alias_separator=-"
        }
        res = await test_client.post("/add/dummy", headers=headers, json=data)

        assert res.status_code == 200
        assert res.json()["data"]["email"] == "foo-com-example-0261-bar@example.com"

    @pytest.mark.anyio
    async def test_list_success(self, client, headers):
        test_client, mock_http = client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"alias": "foo"}]}
        mock_response.raise_for_status = Mock()
        mock_http.get.return_value = mock_response

        res = await test_client.get("/list/example.com", headers=headers)
        assert res.status_code == 200
        assert res.json() == [{"alias": "foo"}]

    @pytest.mark.anyio
    async def test_delete_success(self, client, headers):
        test_client, mock_http = client

        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.raise_for_status = Mock()
        mock_http.delete.return_value = mock_response

        res = await test_client.delete("/delete/foo@example.com", headers=headers)
        assert res.status_code == 204

    @pytest.mark.anyio
    async def test_delete_invalid_email(self, client, headers):
        test_client, _ = client
        res = await test_client.delete("/delete/invalid-email", headers=headers)
        assert res.status_code == 400
