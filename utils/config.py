__author__ = "Baochun Li"

import logging
from collections import namedtuple
import configparser
import argparse
from os import name

class Config:
  _instance = None
  config = configparser.ConfigParser()

  def __new__(cls) -> Any:
    if cls._instance is None:
      parser = argparse.ArgumentParser()
      parser.add_argument('-c','--config', type=str, default='./config.conf', help='The ns.py configuration file')

      Config.args = parser.parse_args()

      cls._instance = super(Config, cls).__new__(cls)
      cls.config.read(Config.args.config)
      cls.extract()
    
    cls._instance

  @staticmethod
  def extract_section(section,fields,defaults):
    params = []

    if section not in Config.config:
      return None

    for i, field in enumerate(fields):
      if isinstance(defaults[i], bool):
        params.append(Config.config[section].getboolean(field, defaults[i]))
      elif isinstance(defaults[i], int):
        params.append(Config.config[section].getint(field, defaults[i]))
      elif isinstance(defaults[i], float):
        params.append(Config.config[section].getfloat(field, defaults[i]))
      else: # string
        params.append(Config.config[section].get(field, defaults[i]))

    return params

  @staticmethod
  def extract():
    fields = [
      'simulation_time',
      'traffic_time',
      'flow_queue_count',
      'subscriber_queue_count',
      'use_constant_bit_rate',
      'mean_interarrival_time',
      'mean_packet_size',
      'use_RED',
      'limit_bytes',
      'flow_queue_pir',
      'buffer_size',
      'max_threshold',
      'min_threshold',
      'max_probability',
      'subscriber_queue_cir',
      'subscriber_queue_pir',
      'group_queue_pir'
    ]

    defaults = (10, 10, 2, 2, True, 0.5, 1000, False, False, 10000, 10, 8, 5, 0.8, 1000, 20000, 40000)
    params = Config.extract_section('HQoS', fields, defaults)
    Config.HQoS = namedtuple('HQoS', fields)(*params)
    
