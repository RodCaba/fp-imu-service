import time
from fp_mqtt_broker import MessageHandler
from src.imu_buffer import IMUBuffer
from typing import Dict, Any
import logging
from fp_orchestrator_utils import OrchestratorClient



class IMUMessageHandler(MessageHandler):
    """
    IMU message handler for processing incoming IMU data messages.
    """
    def __init__(self, imu_buffer: IMUBuffer, config: dict):
        self.imu_buffer = imu_buffer
        self.config = config
        self.orchestrator_client = OrchestratorClient(
            server_address=config['orchestrator']['server_address'],
            timeout=config['orchestrator'].get('timeout', 30)
        )

        # Wait for orchestrator service to be healthy, for a maximum of 10 retries
        retries = 10
        for _ in range(retries):
            if self.orchestrator_client.health_check():
                logging.info("Orchestrator service is healthy")
                break
            logging.warning(f"Retry {_ + 1}/{retries} to connect to orchestrator service")
            logging.warning("Orchestrator service is not healthy, retrying in 5 seconds...")
            time.sleep(5)

        if not self.orchestrator_client.health_check():
            logging.error("Orchestrator service is not healthy after retries, exiting")
            raise RuntimeError("Orchestrator service is not healthy")

    def get_subscribed_topics(self) -> list:
        return [self.config['mqtt']['topics']['data_stream']]

    def handle_message(self, topic: str, payload: Dict[str, Any]):
        """
        Handle incoming MQTT messages.
        """
        try:
            # Get the orchestrator service status
            orchestrator_status = self.orchestrator_client.get_orchestrator_status()
            logging.info(f"Orchestrator status: {orchestrator_status}")

            if topic == self.config['mqtt']['topics']['data_stream']:
                self.handle_data_processing(payload)
        except Exception as e:
            logging.error(f"Failed to process IMU message: {str(e)}")
        
    def handle_data_processing(self, data: Dict[str, Any]):
        """
        Handle data processing requests.
        :param data: Data to be processed.
        """
        try:
            payload = data.get('payload', [])

            if not isinstance(payload, list) or len(payload) == 0:
                raise ValueError("Payload is not a valid list or is empty")

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
