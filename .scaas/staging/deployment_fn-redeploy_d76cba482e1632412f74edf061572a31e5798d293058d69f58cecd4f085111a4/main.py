def handler(event, context):
    return {"quotient": event["a"] / event["b"]}
