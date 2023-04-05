import json
import logging
import argparse

from pipeline.pipeline import Pipeline


def main(args: argparse.Namespace)-> None:
    
    with open(args.config_path, "r") as file:
        app_config = json.load(file)
    
    logging.info("Building the pipeline")
    pipeline = Pipeline(app_config,
                        protolib_path=args.protolib_path,
                        connection_string=args.connection_string)
    
    logging.info("Starting pipeline")
    pipeline.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_path", required=True, type=str)
    parser.add_argument("--protolib_path", required=True, type=str)
    parser.add_argument("--connection_string", required=True, type=int)
    args = parser.parse_args()
    main(args)