def handler(event, context):
    return {
        "nested": event["outer"]["inner"],
        "list_item": event["items"][1],
    }
