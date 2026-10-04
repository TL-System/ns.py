"""YAML conversion and singleton loading preserve user data and retryability."""

import math
import sys

import pytest

from ns.utils.config import Config


@pytest.fixture(autouse=True)
def fresh_config(monkeypatch):
    monkeypatch.setattr(Config, "_instance", None)
    monkeypatch.delenv("config_file", raising=False)


def test_failed_load_can_be_retried_and_success_is_loaded_once(tmp_path, monkeypatch):
    path = tmp_path / "config.yml"
    monkeypatch.setattr(sys, "argv", ["scenario", "--config", str(path)])
    with pytest.raises(FileNotFoundError):
        Config()
    path.write_text("params:\n  rate: 800\n  nested:\n    sizes: [100, 40]\n")
    config = Config()
    assert config.params.rate == 800
    assert config.params.nested.sizes == [100, 40]
    # Loading uses a context manager: the file can be removed after construction.
    path.unlink()
    assert Config() is config


def test_environment_path_overrides_cli_path(tmp_path, monkeypatch):
    path = tmp_path / "config.yml"
    path.write_text("params: {rate: 1600}")
    monkeypatch.setattr(sys, "argv", ["scenario", "-c", "missing.yml"])
    monkeypatch.setenv("config_file", str(path))
    assert Config().params.rate == 1600


@pytest.mark.parametrize("document", ["", "{}", "other: 5"])
def test_empty_or_missing_params_defaults_to_empty_mapping(
    document, tmp_path, monkeypatch
):
    path = tmp_path / "config.yml"
    path.write_text(document)
    monkeypatch.setattr(sys, "argv", ["scenario", "-c", str(path)])
    assert Config().params._asdict() == {}


@pytest.mark.parametrize("document", ["[1, 2]", "params: [1, 2]", "params: null"])
def test_yaml_root_and_params_must_be_mappings(document, tmp_path, monkeypatch):
    path = tmp_path / "config.yml"
    path.write_text(document)
    monkeypatch.setattr(sys, "argv", ["scenario", "-c", str(path)])
    with pytest.raises(ValueError, match="mapping"):
        Config()
    assert Config._instance is None


def test_conversion_retains_non_attribute_keys_and_nested_values():
    converted = Config.namedtuple_from_dict(
        {"valid": [{"child": 3}], "bad-key": {"rate": 800}, 7: "number key"}
    )
    assert converted[7] == "number key"
    assert converted["valid"][0].child == 3
    assert converted["bad-key"].rate == 800
    assert Config.namedtuple_from_dict({"class": 1}) == {"class": 1}


@pytest.mark.parametrize("yaml_key", [".inf", ".nan"])
def test_yaml_numeric_keys_remain_numeric_mappings(
    yaml_key, tmp_path, monkeypatch
):
    path = tmp_path / "config.yml"
    path.write_text(f"params: {{{yaml_key}: {{rate: 800}}}}")
    monkeypatch.setattr(sys, "argv", ["scenario", "-c", str(path)])
    params = Config().params
    assert isinstance(params, dict)
    key = next(iter(params))
    assert isinstance(key, float)
    assert (math.isinf(key) if yaml_key == ".inf" else math.isnan(key))
    # NaN is unequal to itself. Look up the retained key object, and verify that
    # nested values still convert to attributes inside the preserved mapping.
    assert params[key].rate == 800
