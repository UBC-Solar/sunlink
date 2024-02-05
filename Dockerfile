FROM python:3.10

WORKDIR /sunlink

COPY requirements.txt /sunlink

ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/Message.py"
ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/CAN_Msg.py"
ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/GPS_Msg.py"
ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/IMU_Msg.py"
ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/create_message_.py"
ENV PYTHONPATH "${PYTHONPATH}:/sunlink/parser/randomizer.py"


RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "-m", "flask", "--app", "parser.main", "run", "--host=0.0.0.0"]
