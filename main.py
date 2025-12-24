def handler(event, context):
    return {
        "sum": event["a"] + event["b"]
    }
