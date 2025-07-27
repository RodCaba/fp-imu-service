import logging
from fp_orchestrator_utils import OrchestratorClient
from datetime import datetime

class IMUBuffer:
    """Class to manage the IMU data buffer."""
    
    def __init__(self, config, orchestrator_client: OrchestratorClient):
        self.max_size = config['data']['max_buffer_size']
        self.orchestrator_client = orchestrator_client

    def process_sensor_reading(self, reading):
        """Process a single sensor reading and add it to the appropriate buffer."""
        name = reading['sensor_name']
        values = reading['payload']
        device_id = reading.get('device_id', 'unknown')

        try:
          # Add reading to the appropriate buffer based on the sensor name
          self.validate_sensor_values(values, name)
          self.send_to_orchestrator(values, name, device_id)

        except ValueError as e:
          logging.error(f"Invalid sensor reading: {str(e)}")

    def validate_sensor_values(self, values, name):
        """Validate the structure of sensor values."""
        if not isinstance(values, dict):
            raise ValueError("Values must be a JSON object")
        
        # Check for required fields in values
        required_fields = ['x', 'y', 'z']

        if name == 'orientation':
            required_fields = ['qx', 'qy', 'qz', 'qw', 'roll', 'pitch', 'yaw']

        for field in required_fields:
            if field not in values:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure all values are numbers
        for field in values:
            if not isinstance(values[field], (int, float)):
                raise ValueError(f"Field '{field}' must be a number")

    def send_to_orchestrator(self, data, sensor_type, device_id):
        """Send data to the orchestrator service."""
        try:
            response = self.orchestrator_client.send_imu_data(
                device_id=device_id,
                timestamp=int(datetime.now().timestamp()),
                data={
                    'sensor_type': sensor_type,
                    'values': data
                }
            )
            logging.info(f"Data sent to orchestrator: {response}")
        except Exception as e:
            logging.error(f"Failed to send data to orchestrator: {str(e)}")
