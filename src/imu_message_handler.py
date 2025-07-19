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

            # Payload is a list of {'name': str, 'values': dict}

            for sensor_data in payload:
                if 'name' not in sensor_data or 'values' not in sensor_data:
                    raise ValueError("Each sensor data must contain 'name' and 'values' keys")

                sensor_reading = {
                    'sensor_name': sensor_data['name'],
                    'payload': sensor_data['values'],
                }
                # Process each sensor reading
                logging.info(f"Processing sensor reading: {sensor_reading}")
                self.imu_buffer.process_sensor_reading(sensor_reading)

        except Exception as e:
            raise RuntimeError(f"Failed to process data: {str(e)}")
