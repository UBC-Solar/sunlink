import pathlib

from parser.main import create_message
from dotenv import load_dotenv
import threading
from data_tools import PostgresClient
from data_tools.query.data_schema import CANLog, get_sensor_id
import tomllib


load_dotenv()


postgres_client = PostgresClient("can_log_prod")


thread_local_storage = threading.local()    # Per-thread local storage


with open(str(pathlib.Path(__file__).parent.parent / "config" / "postgres.toml"), "rb") as f:
    postgres_targets = tomllib.load(f)
    targets = postgres_targets["config"]["targets"]


def get_session():
    """
    Get the session for the current thread, creating it if necessary.
    """
    if not hasattr(thread_local_storage, 'session'):
        thread_local_storage.session = postgres_client.get_session()
    return thread_local_storage.session


def parse_message(msg):
    """
    Parse a message and
    """    
    local_session = get_session()  # Get the thread-local session
    msgs = []
    if len(msg) == 45:
        msgs.append(msg[:22])                  # Might need to change splitting logic
        msgs.append(msg[23:])                  # Might need to change splitting logic
    else:
        msgs = [msg]

    for msg in msgs:
        # try extracting measurements
        try:
            message = create_message(msg)
            sensor_logs = []

            for i in range(len(message.data["Measurement"])):
                if (measurement := message.data['Measurement'][i]) in targets:
                    sensor_logs.append(CANLog(timestamp=message.data['Timestamp'][i],
                                              sensor_type=get_sensor_id(measurement),
                                              value=message.data['Value'][i]))
            
            if len(sensor_logs) > 0:
                try:
                    local_session.add_all(sensor_logs)
                    local_session.commit()
                except Exception as e:
                    local_session.rollback()
                    print(e)

        except Exception as e:
            print(e)
