FROM python:3.10

WORKDIR /sunlink

COPY requirements.txt /sunlink


RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "-m", "flask", "--app", "parser.main", "run", "--host=0.0.0.0"]
