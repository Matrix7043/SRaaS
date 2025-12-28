import logging

def handler(event, context):
    while True:
        pass
    return {
        "quotient": event["a"]/event["b"]
    }
