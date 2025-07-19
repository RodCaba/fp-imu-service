import logging

class IMUBuffer:
    """Class to manage the IMU data buffer."""
    
    def __init__(self, config):
        self.accelerometer_data_buffer = []
        self.gyroscope_data_buffer = []
        self.gravity_data_buffer = []
        self.total_acceleration_data_buffer = []
        self.orientation_data_buffer = []
        self.max_size = config['data']['max_buffer_size']

    def process_sensor_reading(self, reading):
        """Process a single sensor reading and add it to the appropriate buffer."""
        name = reading['sensor_name']
        values = reading['payload']
        logging.info(f"Processing sensor reading: {name} with values: {values}")
        try:
          # Add reading to the appropriate buffer based on the sensor name
          if name == 'accelerometer':
              self.validate_sensor_values(values, name)
              self.add_to_buffer(values, self.accelerometer_data_buffer)
          elif name == 'gyroscope':
              self.validate_sensor_values(values, name)
              self.add_to_buffer(values, self.gyroscope_data_buffer)
          elif name == 'gravity':
              self.validate_sensor_values(values, name)
              self.add_to_buffer(values, self.gravity_data_buffer)
          elif name == 'totalacceleration':
              self.validate_sensor_values(values, name)
              self.add_to_buffer(values, self.total_acceleration_data_buffer)
          elif name == 'orientation':
              self.validate_sensor_values(values, name)
              self.add_to_buffer(values, self.orientation_data_buffer)
  
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

    def add_to_buffer(self, data, buffer):
        """Add new IMU data to the buffer."""
        if len(buffer) >= self.max_size:
            buffer.pop(0)  # Remove oldest data
        buffer.append(data)

    def get_data(self):
        """Get all buffered IMU data."""
        return {
            'accelerometer': self.accelerometer_data_buffer,
            'gyroscope': self.gyroscope_data_buffer,
            'gravity': self.gravity_data_buffer,
            'total_acceleration': self.total_acceleration_data_buffer,
            'orientation': self.orientation_data_buffer
        }
    
    def get_current_buffer_size(self):
        """Get the total size of all buffers."""
        return {
            'accelerometer': len(self.accelerometer_data_buffer),
            'gyroscope': len(self.gyroscope_data_buffer),
            'gravity': len(self.gravity_data_buffer),
            'total_acceleration': len(self.total_acceleration_data_buffer),
            'orientation': len(self.orientation_data_buffer)
        }

    def clear(self):
        """Clear the buffer."""
        self.accelerometer_data_buffer.clear()
        self.gyroscope_data_buffer.clear()
        self.gravity_data_buffer.clear()
        self.total_acceleration_data_buffer.clear()
        self.orientation_data_buffer.clear()