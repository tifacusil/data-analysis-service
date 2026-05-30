import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session")
def app():
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with patch("app.consul.register"), \
         patch("app.consul.deregister"), \
         patch("app.cache._get_client", return_value=mock_redis):
        from app import create_app
        application = create_app({"TESTING": True})
        yield application


@pytest.fixture
def client(app):
    return app.test_client()
