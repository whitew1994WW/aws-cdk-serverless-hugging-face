import configparser


def ConfigManager():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config

