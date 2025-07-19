from fp_mqtt_broker import MessageHandler
from src.imu_buffer import IMUBuffer
from typing import Dict, Any


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
        try:
            # Transform the message format to match IMUBuffer expectations
            if 'payload' in payload and 'name' in payload and len(payload['payload']) > 0:
                sensor_reading = {
                    'sensor_name': payload['name'],
                    'payload': payload['payload'][0] if isinstance(payload['payload'], list) else payload['payload']
                }
                self.imu_buffer.process_sensor_reading(sensor_reading)
        except Exception as e:
            raise RuntimeError(f"Failed to process IMU message: {str(e)}")