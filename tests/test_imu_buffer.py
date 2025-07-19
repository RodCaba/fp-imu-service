import unittest
import pytest
from unittest.mock import patch

from src.imu_buffer import IMUBuffer

@pytest.mark.unit
class TestIMUBuffer(unittest.TestCase):
    """Test cases for the IMUBuffer class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            'data': {
                'max_buffer_size': 100
            }
        }
        
        # Set up patches for external modules
        self.patcher_logging = patch('src.imu_buffer.logging')
        self.mock_logging = self.patcher_logging.start()
        
        # Create buffer instance
        self.buffer = IMUBuffer(self.config)
        
    def tearDown(self):
        """Clean up patches after each test method."""
        self.patcher_logging.stop()
    
    def test_buffer_initialization(self):
        """Test IMUBuffer initialization."""
        # Verify all buffers are initialized as empty lists
        self.assertEqual(len(self.buffer.accelerometer_data_buffer), 0)
        self.assertEqual(len(self.buffer.gyroscope_data_buffer), 0)
        self.assertEqual(len(self.buffer.gravity_data_buffer), 0)
        self.assertEqual(len(self.buffer.total_acceleration_data_buffer), 0)
        self.assertEqual(len(self.buffer.orientation_data_buffer), 0)
        
        # Verify max_size is set correctly
        self.assertEqual(self.buffer.max_size, 100)
    
    def test_process_sensor_reading_accelerometer(self):
        """Test processing accelerometer sensor reading."""
        reading = {
            'sensor_name': 'accelerometer',
            'payload': {'x': 1.5, 'y': 2.5, 'z': 3.5}
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify data was added to accelerometer buffer
        self.assertEqual(len(self.buffer.accelerometer_data_buffer), 1)
        self.assertEqual(self.buffer.accelerometer_data_buffer[0], {'x': 1.5, 'y': 2.5, 'z': 3.5})
        
        # Verify other buffers remain empty
        self.assertEqual(len(self.buffer.gyroscope_data_buffer), 0)
        self.assertEqual(len(self.buffer.gravity_data_buffer), 0)
    
    def test_process_sensor_reading_gyroscope(self):
        """Test processing gyroscope sensor reading."""
        reading = {
            'sensor_name': 'gyroscope',
            'payload': {'x': 0.1, 'y': 0.2, 'z': 0.3}
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify data was added to gyroscope buffer
        self.assertEqual(len(self.buffer.gyroscope_data_buffer), 1)
        self.assertEqual(self.buffer.gyroscope_data_buffer[0], {'x': 0.1, 'y': 0.2, 'z': 0.3})
    
    def test_process_sensor_reading_gravity(self):
        """Test processing gravity sensor reading."""
        reading = {
            'sensor_name': 'gravity',
            'payload': {'x': 0.0, 'y': 0.0, 'z': 9.8}
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify data was added to gravity buffer
        self.assertEqual(len(self.buffer.gravity_data_buffer), 1)
        self.assertEqual(self.buffer.gravity_data_buffer[0], {'x': 0.0, 'y': 0.0, 'z': 9.8})
    
    def test_process_sensor_reading_total_acceleration(self):
        """Test processing total acceleration sensor reading."""
        reading = {
            'sensor_name': 'totalacceleration',
            'payload': {'x': 2.0, 'y': 3.0, 'z': 4.0}
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify data was added to total acceleration buffer
        self.assertEqual(len(self.buffer.total_acceleration_data_buffer), 1)
        self.assertEqual(self.buffer.total_acceleration_data_buffer[0], {'x': 2.0, 'y': 3.0, 'z': 4.0})
    
    def test_process_sensor_reading_orientation(self):
        """Test processing orientation sensor reading."""
        reading = {
            'sensor_name': 'orientation',
            'payload': {
                'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
                'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
            }
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify data was added to orientation buffer
        self.assertEqual(len(self.buffer.orientation_data_buffer), 1)
        expected_data = {
            'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
            'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
        }
        self.assertEqual(self.buffer.orientation_data_buffer[0], expected_data)
    
    def test_validate_sensor_values_valid_xyz(self):
        """Test validation of valid x,y,z sensor values."""
        values = {'x': 1.0, 'y': 2.0, 'z': 3.0}
        
        # Should not raise any exception
        try:
            self.buffer.validate_sensor_values(values, 'accelerometer')
        except ValueError:
            self.fail("validate_sensor_values raised ValueError unexpectedly!")
    
    def test_validate_sensor_values_valid_orientation(self):
        """Test validation of valid orientation sensor values."""
        values = {
            'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
            'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
        }
        
        # Should not raise any exception
        try:
            self.buffer.validate_sensor_values(values, 'orientation')
        except ValueError:
            self.fail("validate_sensor_values raised ValueError unexpectedly!")
    
    def test_validate_sensor_values_not_dict(self):
        """Test validation fails when values is not a dictionary."""
        values = [1, 2, 3]  # List instead of dict
        
        with self.assertRaises(ValueError) as context:
            self.buffer.validate_sensor_values(values, 'accelerometer')
        
        self.assertEqual(str(context.exception), "Values must be a JSON object")
    
    def test_validate_sensor_values_missing_field_xyz(self):
        """Test validation fails when required x,y,z field is missing."""
        values = {'x': 1.0, 'y': 2.0}  # Missing 'z'
        
        with self.assertRaises(ValueError) as context:
            self.buffer.validate_sensor_values(values, 'accelerometer')
        
        self.assertEqual(str(context.exception), "Missing required field: z")
    
    def test_validate_sensor_values_missing_field_orientation(self):
        """Test validation fails when required orientation field is missing."""
        values = {
            'qx': 0.1, 'qy': 0.2, 'qz': 0.3,  # Missing 'qw'
            'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
        }
        
        with self.assertRaises(ValueError) as context:
            self.buffer.validate_sensor_values(values, 'orientation')
        
        self.assertEqual(str(context.exception), "Missing required field: qw")
    
    def test_validate_sensor_values_non_numeric_value(self):
        """Test validation fails when field value is not numeric."""
        values = {'x': 1.0, 'y': 'invalid', 'z': 3.0}  # 'y' is not numeric
        
        with self.assertRaises(ValueError) as context:
            self.buffer.validate_sensor_values(values, 'accelerometer')
        
        self.assertEqual(str(context.exception), "Field 'y' must be a number")
    
    def test_process_sensor_reading_validation_error(self):
        """Test processing sensor reading with validation error."""
        reading = {
            'sensor_name': 'accelerometer',
            'payload': {'x': 1.0, 'y': 'invalid', 'z': 3.0}  # Invalid 'y' value
        }
        
        self.buffer.process_sensor_reading(reading)
        
        # Verify error was logged
        self.mock_logging.error.assert_called_once_with("Invalid sensor reading: Field 'y' must be a number")
        
        # Verify no data was added to buffer
        self.assertEqual(len(self.buffer.accelerometer_data_buffer), 0)
    
    def test_add_to_buffer_normal(self):
        """Test adding data to buffer when under max size."""
        data = {'x': 1.0, 'y': 2.0, 'z': 3.0}
        buffer = []
        
        self.buffer.add_to_buffer(data, buffer)
        
        self.assertEqual(len(buffer), 1)
        self.assertEqual(buffer[0], data)
    
    def test_add_to_buffer_max_size_reached(self):
        """Test adding data to buffer when max size is reached."""
        # Create a small buffer for testing
        small_config = {'data': {'max_buffer_size': 2}}
        small_buffer = IMUBuffer(small_config)
        
        # Fill buffer to max capacity
        data1 = {'x': 1.0, 'y': 1.0, 'z': 1.0}
        data2 = {'x': 2.0, 'y': 2.0, 'z': 2.0}
        data3 = {'x': 3.0, 'y': 3.0, 'z': 3.0}
        
        buffer = []
        small_buffer.add_to_buffer(data1, buffer)
        small_buffer.add_to_buffer(data2, buffer)
        
        # Verify buffer is at max capacity
        self.assertEqual(len(buffer), 2)
        
        # Add one more item - should remove oldest
        small_buffer.add_to_buffer(data3, buffer)
        
        # Verify buffer size remains at max and oldest item was removed
        self.assertEqual(len(buffer), 2)
        self.assertEqual(buffer[0], data2)  # data1 was removed
        self.assertEqual(buffer[1], data3)  # data3 was added
    
    def test_get_data(self):
        """Test getting all buffered data."""
        # Add some test data to different buffers
        accel_data = {'x': 1.0, 'y': 2.0, 'z': 3.0}
        gyro_data = {'x': 0.1, 'y': 0.2, 'z': 0.3}
        
        self.buffer.accelerometer_data_buffer.append(accel_data)
        self.buffer.gyroscope_data_buffer.append(gyro_data)
        
        result = self.buffer.get_data()
        
        expected_result = {
            'accelerometer': [accel_data],
            'gyroscope': [gyro_data],
            'gravity': [],
            'total_acceleration': [],
            'orientation': []
        }
        
        self.assertEqual(result, expected_result)
    
    def test_get_current_buffer_size(self):
        """Test getting current buffer sizes."""
        # Add some test data
        self.buffer.accelerometer_data_buffer.append({'x': 1.0, 'y': 2.0, 'z': 3.0})
        self.buffer.accelerometer_data_buffer.append({'x': 2.0, 'y': 3.0, 'z': 4.0})
        self.buffer.gyroscope_data_buffer.append({'x': 0.1, 'y': 0.2, 'z': 0.3})
        
        result = self.buffer.get_current_buffer_size()
        
        expected_result = {
            'accelerometer': 2,
            'gyroscope': 1,
            'gravity': 0,
            'total_acceleration': 0,
            'orientation': 0
        }
        
        self.assertEqual(result, expected_result)
    
    def test_clear(self):
        """Test clearing all buffers."""
        # Add some test data to all buffers
        test_data = {'x': 1.0, 'y': 2.0, 'z': 3.0}
        orientation_data = {
            'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
            'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
        }
        
        self.buffer.accelerometer_data_buffer.append(test_data)
        self.buffer.gyroscope_data_buffer.append(test_data)
        self.buffer.gravity_data_buffer.append(test_data)
        self.buffer.total_acceleration_data_buffer.append(test_data)
        self.buffer.orientation_data_buffer.append(orientation_data)
        
        # Verify data exists
        self.assertGreater(len(self.buffer.accelerometer_data_buffer), 0)
        self.assertGreater(len(self.buffer.gyroscope_data_buffer), 0)
        
        # Clear buffers
        self.buffer.clear()
        
        # Verify all buffers are empty
        self.assertEqual(len(self.buffer.accelerometer_data_buffer), 0)
        self.assertEqual(len(self.buffer.gyroscope_data_buffer), 0)
        self.assertEqual(len(self.buffer.gravity_data_buffer), 0)
        self.assertEqual(len(self.buffer.total_acceleration_data_buffer), 0)
        self.assertEqual(len(self.buffer.orientation_data_buffer), 0)
    
    def test_unknown_sensor_name(self):
        """Test processing reading with unknown sensor name."""
        reading = {
            'sensor_name': 'unknown_sensor',
            'payload': {'x': 1.0, 'y': 2.0, 'z': 3.0}
        }
        
        # Should not raise an exception, just do nothing
        self.buffer.process_sensor_reading(reading)
        
        # Verify no data was added to any buffer
        sizes = self.buffer.get_current_buffer_size()
        for size in sizes.values():
            self.assertEqual(size, 0)
    
    def test_multiple_readings_same_sensor(self):
        """Test processing multiple readings for the same sensor."""
        readings = [
            {'sensor_name': 'accelerometer', 'payload': {'x': 1.0, 'y': 2.0, 'z': 3.0}},
            {'sensor_name': 'accelerometer', 'payload': {'x': 2.0, 'y': 3.0, 'z': 4.0}},
            {'sensor_name': 'accelerometer', 'payload': {'x': 3.0, 'y': 4.0, 'z': 5.0}}
        ]
        
        for reading in readings:
            self.buffer.process_sensor_reading(reading)
        
        # Verify all readings were added
        self.assertEqual(len(self.buffer.accelerometer_data_buffer), 3)
        self.assertEqual(self.buffer.accelerometer_data_buffer[0], {'x': 1.0, 'y': 2.0, 'z': 3.0})
        self.assertEqual(self.buffer.accelerometer_data_buffer[1], {'x': 2.0, 'y': 3.0, 'z': 4.0})
        self.assertEqual(self.buffer.accelerometer_data_buffer[2], {'x': 3.0, 'y': 4.0, 'z': 5.0})
    
    def test_mixed_sensor_readings(self):
        """Test processing readings from different sensors."""
        readings = [
            {'sensor_name': 'accelerometer', 'payload': {'x': 1.0, 'y': 2.0, 'z': 3.0}},
            {'sensor_name': 'gyroscope', 'payload': {'x': 0.1, 'y': 0.2, 'z': 0.3}},
            {'sensor_name': 'gravity', 'payload': {'x': 0.0, 'y': 0.0, 'z': 9.8}},
            {'sensor_name': 'orientation', 'payload': {
                'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
                'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
            }}
        ]
        
        for reading in readings:
            self.buffer.process_sensor_reading(reading)
        
        # Verify each sensor type has one reading
        sizes = self.buffer.get_current_buffer_size()
        self.assertEqual(sizes['accelerometer'], 1)
        self.assertEqual(sizes['gyroscope'], 1)
        self.assertEqual(sizes['gravity'], 1)
        self.assertEqual(sizes['orientation'], 1)
        self.assertEqual(sizes['total_acceleration'], 0)  # Not used in this test
