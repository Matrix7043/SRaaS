FROM python:3.11-slim

WORKDIR /function

COPY runner.py /runner.py

ENTRYPOINT [ "python", "/runner.py" ]
