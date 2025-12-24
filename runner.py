import importlib
import json
import sys

sys.path.insert(0, "/function")

event_raw = sys.stdin.read()

if not event_raw:
    event = {}

else:
    event = json.loads(event_raw)

handler_path = sys.argv[1]

module_name, func_name = handler_path.rsplit(".", 1)

module = importlib.import_module(module_name)

handler = getattr(module, func_name)

result = handler(event, {})

print(json.dumps(result))
