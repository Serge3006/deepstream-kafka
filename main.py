import os
import json
import logging

from pipeline import Pipeline


def main():
    
    config_pth = "configs/app_config.json"
    with open(config_pth, "r") as file:
        app_config = json.load(file)
    
    logging.info("Building the pipeline")
    pipeline = Pipeline(app_config)
    
    logging.info("Starting pipeline")
    pipeline.run()


if __name__ == "__main__":
    main()