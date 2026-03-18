import tempfile

from potato.flask_server import create_app
from potato.server_utils.config_module import config, clear_config


def _build_test_config(base_path: str) -> dict:
    task_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()

    return {
        "annotation_task_name": "Base Path Test",
        "alert_time_each_instance": 1000,
        "annotation_schemes": [
            {
                "name": "test_scheme",
                "annotation_type": "radio",
                "labels": ["yes", "no"],
                "description": "Pick one",
            }
        ],
        "base_html_template": "base_template.html",
        "customjs": None,
        "customjs_hostname": None,
        "data_files": [],
        "debug": False,
        "header_file": "base_template.html",
        "html_layout": "base_template.html",
        "item_properties": {
            "id_key": "id",
            "text_key": "text",
        },
        "output_annotation_dir": output_dir,
        "persist_sessions": False,
        "require_password": True,
        "server": {
            "base_path": base_path,
        },
        "site_dir": "potato/templates",
        "site_file": "base_template.html",
        "task_dir": task_dir,
        "user_config": {
            "allow_all_users": True,
            "users": [],
        },
    }


def test_home_page_renders_prefixed_urls_under_base_path():
    original_config = dict(config)
    clear_config()
    config.update(_build_test_config("/app1"))

    try:
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        response = client.get("/app1/")

        assert response.status_code == 200
        assert b'data-base-path="/app1"' in response.data
        assert b'action="/app1/auth"' in response.data
        assert b'/app1/static/styles.css' in response.data
    finally:
        clear_config()
        config.update(original_config)


def test_home_page_supports_proxy_stripping_base_path():
    original_config = dict(config)
    clear_config()
    config.update(_build_test_config("/app2"))

    try:
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        response = client.get("/")

        assert response.status_code == 200
        assert b'data-base-path="/app2"' in response.data
        assert b'action="/app2/auth"' in response.data
        assert b'/app2/static/styles.css' in response.data
    finally:
        clear_config()
        config.update(original_config)
