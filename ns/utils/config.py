"""Implements a simple configuration parser that reads runtime parameters
from a YAML configuration file (which is easier to work on than JSON).
"""
import argparse
import os
from collections import OrderedDict, namedtuple

import yaml


class Config:
    """
    Retrieving configuration parameters by parsing a configuration file
    using the YAML configuration file parser.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            parser = argparse.ArgumentParser()
            parser.add_argument('-c',
                                '--config',
                                type=str,
                                default='./config.yml',
                                help='ns.py configuration file.')

            args = parser.parse_args()
            Config.args = args

            cls._instance = super(Config, cls).__new__(cls)

            if 'config_file' in os.environ:
                filename = os.environ['config_file']
            else:
                filename = args.config

            with open(filename, 'r') as config_file:
                config = yaml.load(config_file, Loader=yaml.FullLoader)

            Config.params = Config.namedtuple_from_dict(config['params'])

        return cls._instance

    @staticmethod
    def namedtuple_from_dict(obj):
        """Creates a named tuple from a dictionary."""
        if isinstance(obj, dict):
            fields = sorted(obj.keys())
            namedtuple_type = namedtuple(typename='Config',
                                         field_names=fields,
                                         rename=True)
            field_value_pairs = OrderedDict(
                (str(field), Config.namedtuple_from_dict(obj[field]))
                for field in fields)
            try:
                return namedtuple_type(**field_value_pairs)
            except TypeError:
                # Cannot create namedtuple instance so fallback to dict (invalid attribute names)
                return dict(**field_value_pairs)
        elif isinstance(obj, (list, set, tuple, frozenset)):
            return [Config.namedtuple_from_dict(item) for item in obj]
        else:
            return obj
