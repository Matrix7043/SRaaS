import logging

def handler(event, context):
    print("Hello from print")
    logging.info("Hello from logging")
    logging.error("Hello from error logging")
    return {
        "quotient": event["a"]/event["b"]
    }
