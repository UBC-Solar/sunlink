FROM python:3.10

WORKDIR /src

COPY requirements.txt /src
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "-m", "flask", "--app", "parser", "run", "--host=0.0.0.0", "--debug"]
