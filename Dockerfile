FROM python:3.10

WORKDIR /link_telemetry

COPY requirements.txt /link_telemetry
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "-m", "flask", "--app", "parser", "run", "--host=0.0.0.0"]
