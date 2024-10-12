from sqlalchemy import create_engine, Column, Integer, Float, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from parser.main import create_message
from dotenv import load_dotenv
import os
import threading
from data_tools import PostgresClient

load_dotenv()

POSTGRESQL_USERNAME = os.getenv("POSTGRESQL_USERNAME")
POSTGRESQL_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
POSTGRESQL_DATABASE = os.getenv("POSTGRESQL_DATABASE")
POSTGRESQL_ADDRESS  = os.getenv("POSTGRESQL_ADDRESS")

DATABASE_URL = f"postgresql://{POSTGRESQL_USERNAME}:{POSTGRESQL_PASSWORD}@{POSTGRESQL_ADDRESS}:5432/{POSTGRESQL_DATABASE}"

print(DATABASE_URL)

engine = create_engine(DATABASE_URL)

Base = declarative_base()

class CANLog(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True)
    timestamp = Column(Float, nullable=False)
    sensor_type = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('timestamp', 'sensor_type', name='unique_timestamp_sensor_type'),
    )


Base.metadata.create_all(engine)            # Only needs to be called once, but has no effect if it was already called


Session = sessionmaker(bind=engine)         # Session builder


thread_local_storage = threading.local()    # Per-thread local storage 


def get_session():
    """
    Get the session for the current thread, creating it if necessary.
    """
    if not hasattr(thread_local_storage, 'session'):
        thread_local_storage.session = Session()
    return thread_local_storage.session


targets = ["BatteryCurrent", "BatteryVoltage", "VoltageofLeast" ]


sensor_encodings = {
    "TotalPackVoltage": 0,
    "BatteryCurrent": 1,
    "BatteryVoltage": 2,
    "VehicleVelocity": 3,
    "PackCurrent": 4,
    "BatteryCurrentDirection": 5,
    "VoltageofLeast": 6
}


def parse_message(msg):
    """
    Parses incoming request and sends back the parsed result.
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
                    sensor_logs.append(CANLog(timestamp=message.data['Timestamp'][i], sensor_type=sensor_encodings[measurement], value=message.data['Value'][i]))
            
            if len(sensor_logs) > 0:
                try:
                    local_session.add_all(sensor_logs)
                    local_session.commit()
                except Exception as e:
                    local_session.rollback()
                    print(e)

        except Exception as e:
            print(e)
