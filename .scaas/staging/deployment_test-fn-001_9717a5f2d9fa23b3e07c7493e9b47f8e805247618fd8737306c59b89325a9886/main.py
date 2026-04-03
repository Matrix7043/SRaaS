import socket
def handler(event, context):
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return {"network": True}
    except OSError:
        return {"network": False}
