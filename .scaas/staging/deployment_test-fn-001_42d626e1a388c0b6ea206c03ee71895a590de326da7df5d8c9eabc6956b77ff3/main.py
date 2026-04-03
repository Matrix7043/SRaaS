import logging
logging.basicConfig(level=logging.INFO)

def handler(event, context):
    print("hello from stdout")
    logging.info("hello from logging")
    return {"ok": True}
