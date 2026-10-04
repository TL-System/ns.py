"""Implements a simple configuration parser that reads runtime parameters
from a YAML configuration file (which is easier to work on than JSON).
"""

import argparse
import os
from collections import namedtuple
from typing import Any, ClassVar, Self

import yaml


class Config:
    """
    Retrieving configuration parameters by parsing a configuration file
    using the YAML configuration file parser. The first successful load is
    retained for the process. Missing ``params`` defaults to an empty mapping;
    explicit ``params`` and the document root must be mappings.
    """

    _instance = None
    params: ClassVar[Any]
    args: ClassVar[argparse.Namespace]

    def __new__(cls) -> Self:
        if cls._instance is None:
            parser = argparse.ArgumentParser()
            parser.add_argument(
                "-c",
                "--config",
                type=str,
                default="./config.yml",
                help="ns.py configuration file.",
            )

            args = parser.parse_args()
            if "config_file" in os.environ:
                filename = os.environ["config_file"]
            else:
                filename = args.config

            with open(filename, "r") as config_file:
                config = yaml.safe_load(config_file)
            if config is None:
                config = {}
            if not isinstance(config, dict):
                raise ValueError("Configuration root must be a mapping.")
            params = config.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("Configuration params must be a mapping.")

            # Publish only a successful load. A missing or malformed file must
            # not leave a half-created singleton that prevents a later retry.
            cls.params = Config.namedtuple_from_dict(params)
            cls.args = args
            cls._instance = super().__new__(cls)

        return cls._instance

    @staticmethod
    def namedtuple_from_dict(obj: Any) -> Any:
        """Expose valid mapping keys as attributes; retain other mappings as dicts."""
        if isinstance(obj, dict):
            values = {
                key: Config.namedtuple_from_dict(value) for key, value in obj.items()
            }
            # YAML allows numeric keys and names such as 'link-rate'. Preserve
            # those keys rather than renaming them or coercing them to strings.
            # namedtuple stringifies its field names, so even numeric infinity
            # and NaN could otherwise become valid-looking attribute names.
            if any(not isinstance(key, str) for key in values):
                return values
            try:
                fields = sorted(values)
                namedtuple_type = namedtuple("Config", fields)  # ty: ignore[mismatched-type-name]
                return namedtuple_type(*(values[field] for field in fields))
            except (TypeError, ValueError):
                return values
        elif isinstance(obj, (list, set, tuple, frozenset)):
            return [Config.namedtuple_from_dict(item) for item in obj]
        else:
            return obj
