"""
Selenium UI tests for the pairwise edit-classification example.

These tests cover the custom pair-builder workflow:
- add multiple direction/target annotations
- remove an existing annotation
- use the standalone N/A option and verify persistence on reload
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options as ChromeOptions

from tests.helpers.flask_test_setup import FlaskTestServer
from tests.helpers.port_manager import find_free_port


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_LAYOUT = PROJECT_ROOT / "examples" / "classification" / "pairwise-edit-classification" / "layouts" / "task_layout.html"


class TestPairwiseEditClassificationUI:
    """Browser tests for the structured pairwise edit-classification workflow."""

    @classmethod
    def setup_class(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="pairwise_edit_classification_test_")
        cls.port = find_free_port()

        data_dir = Path(cls.test_dir) / "data"
        layouts_dir = Path(cls.test_dir) / "layouts"
        data_dir.mkdir(parents=True, exist_ok=True)
        layouts_dir.mkdir(parents=True, exist_ok=True)

        data_file = data_dir / "pairwise_data.jsonl"
        test_data = [
            {
                "id": "pair_1",
                "text": [
                    "The detective questions the suspect in a rainy alley.",
                    "The detective questions the suspect in a rainy alley, then discovers a hidden map."
                ],
            },
            {
                "id": "pair_2",
                "text": [
                    "Write a polite assistant reply.",
                    "Write a terse pirate captain reply in bullet points."
                ],
            },
        ]
        with data_file.open("w", encoding="utf-8") as outfile:
            for item in test_data:
                outfile.write(json.dumps(item) + "\n")

        shutil.copy(EXAMPLE_LAYOUT, layouts_dir / "task_layout.html")

        config_file = Path(cls.test_dir) / "config.yaml"
        config_content = f"""
port: {cls.port}
server_name: Pairwise Edit Classification Test
annotation_task_name: Prompt Edit Classification Test
task_dir: {cls.test_dir}
site_dir: default
task_layout: layouts/task_layout.html
output_annotation_dir: {cls.test_dir}/annotation_output/
output_annotation_format: jsonl

data_files:
  - data/pairwise_data.jsonl

item_properties:
  id_key: id
  text_key: text

list_as_text:
  text_list_prefix_type: alphabet

user_config:
  allow_all_users: true
  users: []

annotation_schemes:
  - annotation_type: pairwise
    name: pair_display
    description: Prompt pair display
    mode: binary
    items_key: text
    item_display_mode: side_by_side
    show_item_diff: true
    diff_granularity: word
    diff_ignore_case: true
    diff_ignore_punctuation: true
    item_labels:
      - Prompt A
      - Prompt B
    labels:
      - A
      - B
    sequential_key_binding: false
    label_requirement:
      required: false

  - annotation_type: text
    name: edit_classification
    description: Edit classification
    label_requirement:
      required: true
"""
        config_file.write_text(config_content, encoding="utf-8")

        cls.server = FlaskTestServer(port=cls.port, debug=False, config_file=str(config_file))
        started = cls.server.start_server()
        if not started:
            raise RuntimeError(f"Failed to start Flask server on port {cls.port}")

        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        cls.chrome_options = chrome_options

    @classmethod
    def teardown_class(cls):
        if hasattr(cls, "server"):
            cls.server.stop_server()
        if hasattr(cls, "test_dir") and os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setup_method(self):
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
        self.test_user = f"edit_classifier_{int(time.time() * 1000)}"
        self._login()

    def teardown_method(self):
        if hasattr(self, "driver"):
            self.driver.quit()

    def _login(self):
        self.driver.get(f"{self.server.base_url}/")
        self.wait.until(EC.presence_of_element_located((By.ID, "login-email")))
        username_field = self.driver.find_element(By.ID, "login-email")
        username_field.clear()
        username_field.send_keys(self.test_user)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(EC.presence_of_element_located((By.ID, "edit_classification")))
        self.wait.until(lambda driver: driver.find_element(By.ID, "edit-classification-na").is_enabled())

    def _get_hidden_state(self):
        hidden_input = self.driver.find_element(By.ID, "edit_classification_selection")
        raw_value = hidden_input.get_attribute("value")
        if not raw_value:
            return raw_value, {"na": False, "pairs": []}
        return raw_value, json.loads(raw_value)

    def _add_pair(self, direction, target):
        Select(self.driver.find_element(By.ID, "edit-direction-select")).select_by_value(direction)
        Select(self.driver.find_element(By.ID, "edit-target-select")).select_by_value(target)
        add_button = self.driver.find_element(By.ID, "edit-classification-add")
        assert add_button.is_enabled()
        add_button.click()
        self.wait.until(lambda driver: len(driver.find_elements(By.CLASS_NAME, "edit-classification-remove-btn")) >= 1)

    def test_add_and_remove_direction_target_pairs(self):
        self._add_pair("ADD", "plot")
        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "ADD", "target": "plot"}],
        }

        self._add_pair("CHANGE", "dialogue")
        self.wait.until(lambda driver: len(driver.find_elements(By.CLASS_NAME, "edit-classification-remove-btn")) == 2)
        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [
                {"direction": "ADD", "target": "plot"},
                {"direction": "CHANGE", "target": "dialogue"},
            ],
        }

        remove_buttons = self.driver.find_elements(By.CLASS_NAME, "edit-classification-remove-btn")
        remove_buttons[0].click()
        self.wait.until(lambda driver: len(driver.find_elements(By.CLASS_NAME, "edit-classification-remove-btn")) == 1)

        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        }

    def test_remove_immediately_after_add_clears_last_pair(self):
        self._add_pair("ADD", "plot")
        remove_button = self.driver.find_element(By.CLASS_NAME, "edit-classification-remove-btn")
        remove_button.click()

        self.wait.until(lambda driver: "No annotations added yet." in driver.find_element(By.ID, "edit-classification-list").text)
        raw_value, state = self._get_hidden_state()
        assert raw_value == ""
        assert state == {"na": False, "pairs": []}

    def test_removing_last_pair_does_not_restore_previous_pair(self):
        self._add_pair("ADD", "plot")
        self._add_pair("CHANGE", "dialogue")

        remove_buttons = self.driver.find_elements(By.CLASS_NAME, "edit-classification-remove-btn")
        remove_buttons[0].click()
        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value")) == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        })

        last_remove_button = self.driver.find_element(By.CLASS_NAME, "edit-classification-remove-btn")
        last_remove_button.click()

        self.wait.until(lambda driver: "No annotations added yet." in driver.find_element(By.ID, "edit-classification-list").text)
        raw_value, state = self._get_hidden_state()
        assert raw_value == ""
        assert state == {"na": False, "pairs": []}

    def test_na_toggle_clears_pairs_and_restores_after_reload(self):
        self._add_pair("REMOVE", "setting")
        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        na_button.click()

        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value"))["na"] is True)
        raw_value, state = self._get_hidden_state()
        assert raw_value
        assert state == {"na": True, "pairs": []}

        direction_select = self.driver.find_element(By.ID, "edit-direction-select")
        target_select = self.driver.find_element(By.ID, "edit-target-select")
        assert not direction_select.is_enabled()
        assert not target_select.is_enabled()

        time.sleep(1.0)
        self.driver.refresh()

        self.wait.until(EC.presence_of_element_located((By.ID, "edit_classification")))
        self.wait.until(lambda driver: driver.find_element(By.ID, "edit_classification_selection").get_attribute("value") != "")
        _, state = self._get_hidden_state()
        assert state == {"na": True, "pairs": []}

        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        assert "is-active" in na_button.get_attribute("class")

    def test_clearing_na_does_not_return_after_navigation(self):
        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        na_button.click()
        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value"))["na"] is True)

        clear_button = self.driver.find_element(By.CSS_SELECTOR, ".edit-classification-remove-btn[data-action='clear-na']")
        clear_button.click()
        self.wait.until(lambda driver: driver.find_element(By.ID, "edit_classification_selection").get_attribute("value") == "")

        self._add_pair("CHANGE", "dialogue")
        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        }

    def test_saved_na_can_be_cleared_after_reload(self):
        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        na_button.click()
        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value"))["na"] is True)

        time.sleep(1.0)
        self.driver.refresh()

        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".edit-classification-remove-btn[data-action='clear-na']")))
        clear_button = self.driver.find_element(By.CSS_SELECTOR, ".edit-classification-remove-btn[data-action='clear-na']")
        clear_button.click()

        self.wait.until(lambda driver: driver.find_element(By.ID, "edit_classification_selection").get_attribute("value") == "")
        time.sleep(0.5)
        raw_value, state = self._get_hidden_state()
        assert raw_value == ""
        assert state == {"na": False, "pairs": []}
        self._add_pair("CHANGE", "dialogue")
        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        }

    def test_rerender_does_not_restore_cleared_na(self):
        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        na_button.click()
        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value"))["na"] is True)

        clear_button = self.driver.find_element(By.CSS_SELECTOR, ".edit-classification-remove-btn[data-action='clear-na']")
        clear_button.click()
        self.wait.until(lambda driver: driver.find_element(By.ID, "edit_classification_selection").get_attribute("value") == "")

        self.driver.execute_script("""
            if (typeof window.__pairwiseEditClassificationRender === 'function') {
                window.__pairwiseEditClassificationRender(true);
            }
        """)

        self.wait.until(lambda driver: "No annotations added yet." in driver.find_element(By.ID, "edit-classification-list").text)
        self._add_pair("CHANGE", "dialogue")
        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        }

    def test_stale_instance_loaded_event_does_not_restore_cleared_na(self):
        na_button = self.driver.find_element(By.ID, "edit-classification-na")
        na_button.click()
        self.wait.until(lambda driver: json.loads(driver.find_element(By.ID, "edit_classification_selection").get_attribute("value"))["na"] is True)

        clear_button = self.driver.find_element(By.CSS_SELECTOR, ".edit-classification-remove-btn[data-action='clear-na']")
        clear_button.click()
        self.wait.until(lambda driver: driver.find_element(By.ID, "edit_classification_selection").get_attribute("value") == "")

        self.driver.execute_script("""
            currentAnnotations.edit_classification = {
                selection: JSON.stringify({ na: true, pairs: [] })
            };
            document.dispatchEvent(new CustomEvent('potato:instance-loaded', {
                detail: {
                    instanceId: document.getElementById('instance_id').value,
                    timestamp: Date.now()
                }
            }));
        """)

        time.sleep(0.25)
        raw_value, state = self._get_hidden_state()
        assert raw_value == ""
        assert state == {"na": False, "pairs": []}

        first_instance_text = self.driver.find_element(By.ID, "instance-text").text
        self.driver.find_element(By.ID, "next-btn").click()
        self.wait.until(lambda driver: driver.find_element(By.ID, "instance-text").text != first_instance_text)

        self.driver.find_element(By.ID, "prev-btn").click()
        self.wait.until(lambda driver: driver.find_element(By.ID, "instance-text").text == first_instance_text)

        _, state = self._get_hidden_state()
        assert state == {
            "na": False,
            "pairs": [{"direction": "CHANGE", "target": "dialogue"}],
        }
