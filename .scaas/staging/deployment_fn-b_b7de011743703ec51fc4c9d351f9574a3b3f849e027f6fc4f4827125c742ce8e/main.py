def handler(event, context):
    return {"owner": "B", "val": event["x"] * 2}
