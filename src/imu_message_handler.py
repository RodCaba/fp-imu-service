from fp_mqtt_broker import MessageHandler
from src.imu_buffer import IMUBuffer
from typing import Dict, Any
import logging


class IMUMessageHandler(MessageHandler):
    """
    IMU message handler for processing incoming IMU data messages.
    """
    def __init__(self, imu_buffer: IMUBuffer, config: dict):
        self.imu_buffer = imu_buffer
        self.config = config

    def get_subscribed_topics(self) -> list:
        return [self.config['mqtt']['topics']['data_stream']]

    def handle_message(self, topic: str, payload: Dict[str, Any]):
        """
        Handle incoming MQTT messages.
        """
        try:
          if topic == self.config['mqtt']['topics']['data_stream']:
              self.handle_data_processing(payload)
        except Exception as e:
            raise RuntimeError(f"Failed to process IMU message: {str(e)}")
        
    def handle_data_processing(self, data: Dict[str, Any]):
        """
        Handle data processing requests.
        :param data: Data to be processed.
        """
        try:
            payload = data.get('payload', {})

            if not payload:
                raise ValueError("Payload is empty or missing in the data")

            logging.info(f"Processing data: {payload}")
            if 'name' not in payload or 'values' not in payload:
                raise ValueError("Payload must contain 'name' and 'values' keys")

            # Process the sensor reading
            sensor_reading = {
                'sensor_name': payload['name'],
                'payload': payload['values'],
            }
            self.imu_buffer.process_sensor_reading(sensor_reading)
        except Exception as e:
            raise RuntimeError(f"Failed to process data: {str(e)}")
