import unittest
from unittest.mock import patch, MagicMock
import json

from src.mqtt_broker.mqtt_broker import MQTTBroker
from src.imu_buffer import IMUBuffer


class TestMQTTBrokerIMUBufferIntegration(unittest.TestCase):
    """Integration tests for MQTTBroker and IMUBuffer interaction after fix."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            'mqtt': {
                'broker_host': 'localhost',
                'broker_port': 1883,
                'topics': {
                    'recording_control': 'imu/recording/control',
                    'data_stream': 'imu/data/stream',
                    'status': 'imu/status'
                },
                'client_id': 'test_client'
            },
            'data': {
                'max_buffer_size': 100
            }
        }
        
        # Set up patches for external modules
        self.patcher_logging = patch('src.mqtt_broker.mqtt_broker.logging')
        self.mock_logging = self.patcher_logging.start()
        
        self.patcher_time = patch('src.mqtt_broker.mqtt_broker.time')
        self.mock_time = self.patcher_time.start()
        self.mock_time.time.return_value = 1234567890.0
        
        self.patcher_socket = patch('src.mqtt_broker.mqtt_broker.socket')
        self.mock_socket = self.patcher_socket.start()
        
        self.patcher_imu_logging = patch('src.imu_buffer.logging')
        self.mock_imu_logging = self.patcher_imu_logging.start()
        
        # Create mock MQTT client
        self.mock_mqtt_client = MagicMock()
        
        # Create real IMU buffer for integration testing
        self.imu_buffer = IMUBuffer(self.config)
        
        # Create MQTT broker with real IMU buffer
        self.broker = MQTTBroker(self.config, self.mock_mqtt_client, self.imu_buffer)
        
    def tearDown(self):
        """Clean up patches after each test method."""
        self.patcher_logging.stop()
        self.patcher_time.stop()
        self.patcher_socket.stop()
        self.patcher_imu_logging.stop()
    
    def test_integration_fix_single_sensor_reading(self):
        """Test that the MQTT broker now successfully sends data to IMU buffer."""
        # Test message with single data point
        mqtt_payload = {
            'deviceId': 'test_device_123',
            'payload': [{'x': 1.5, 'y': 2.5, 'z': 3.5}],
            'name': 'accelerometer'
        }
        
        # Create mock MQTT message
        mock_message = MagicMock()
        mock_message.topic = self.config['mqtt']['topics']['data_stream']
        mock_message.payload.decode.return_value = json.dumps(mqtt_payload)
        
        # Simulate receiving the message
        self.broker.on_message(None, None, mock_message)
        
        # Verify data was successfully processed and stored
        buffer_sizes = self.imu_buffer.get_current_buffer_size()
        self.assertEqual(buffer_sizes['accelerometer'], 1)
        self.assertEqual(buffer_sizes['gyroscope'], 0)
        
        # Verify the actual data stored
        buffered_data = self.imu_buffer.get_data()
        self.assertEqual(buffered_data['accelerometer'][0], {'x': 1.5, 'y': 2.5, 'z': 3.5})
        
        # Verify no errors were logged
        self.mock_imu_logging.error.assert_not_called()
        
        print("✅ INTEGRATION FIX SUCCESSFUL: Single sensor reading works!")
    
    def test_integration_fix_multiple_sensor_readings(self):
        """Test that multiple data points in one message are processed correctly."""
        # Test message with multiple data points
        mqtt_payload = {
            'deviceId': 'test_device_456',
            'payload': [
                {'x': 1.0, 'y': 2.0, 'z': 3.0},
                {'x': 4.0, 'y': 5.0, 'z': 6.0},
                {'x': 7.0, 'y': 8.0, 'z': 9.0}
            ],
            'name': 'gyroscope'
        }
        
        mock_message = MagicMock()
        mock_message.topic = self.config['mqtt']['topics']['data_stream']
        mock_message.payload.decode.return_value = json.dumps(mqtt_payload)
        
        # Process the message
        self.broker.on_message(None, None, mock_message)
        
        # Verify all data points were processed
        buffer_sizes = self.imu_buffer.get_current_buffer_size()
        self.assertEqual(buffer_sizes['gyroscope'], 3)
        self.assertEqual(buffer_sizes['accelerometer'], 0)
        
        # Verify the actual data stored
        buffered_data = self.imu_buffer.get_data()
        expected_data = [
            {'x': 1.0, 'y': 2.0, 'z': 3.0},
            {'x': 4.0, 'y': 5.0, 'z': 6.0},
            {'x': 7.0, 'y': 8.0, 'z': 9.0}
        ]
        self.assertEqual(buffered_data['gyroscope'], expected_data)
        
        # Verify no errors were logged
        self.mock_imu_logging.error.assert_not_called()
        
        print("✅ INTEGRATION FIX SUCCESSFUL: Multiple sensor readings work!")
    
    def test_integration_fix_all_sensor_types(self):
        """Test that all sensor types work with the integration fix."""
        test_cases = [
            {
                'name': 'accelerometer',
                'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}]
            },
            {
                'name': 'gyroscope', 
                'payload': [{'x': 0.1, 'y': 0.2, 'z': 0.3}]
            },
            {
                'name': 'gravity',
                'payload': [{'x': 0.0, 'y': 0.0, 'z': 9.8}]
            },
            {
                'name': 'totalacceleration',
                'payload': [{'x': 2.0, 'y': 3.0, 'z': 4.0}]
            },
            {
                'name': 'orientation',
                'payload': [{
                    'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
                    'roll': 15.0, 'pitch': 30.0, 'yaw': 45.0
                }]
            }
        ]
        
        for test_case in test_cases:
            # Clear buffer for clean test
            self.imu_buffer.clear()
            self.mock_imu_logging.reset_mock()
            
            mqtt_payload = {
                'deviceId': f'test_device_{test_case["name"]}',
                'payload': test_case['payload'],
                'name': test_case['name']
            }
            
            mock_message = MagicMock()
            mock_message.topic = self.config['mqtt']['topics']['data_stream']
            mock_message.payload.decode.return_value = json.dumps(mqtt_payload)
            
            # Process the message
            self.broker.on_message(None, None, mock_message)
            
            # Verify success
            buffer_sizes = self.imu_buffer.get_current_buffer_size()
            sensor_buffer_key = test_case['name']
            if sensor_buffer_key == 'totalacceleration':
                sensor_buffer_key = 'total_acceleration'
            
            self.assertEqual(buffer_sizes[sensor_buffer_key], 1, 
                           f"Sensor {test_case['name']} should have 1 reading")
            
            # Verify no errors
            self.mock_imu_logging.error.assert_not_called()
            
            print(f"✅ SENSOR {test_case['name'].upper()}: Integration fix works!")
    
    def test_integration_before_vs_after_comparison(self):
        """Test comparing old behavior vs new behavior."""
        mqtt_payload = {
            'deviceId': 'comparison_test',
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        }
        
        mock_message = MagicMock()
        mock_message.topic = self.config['mqtt']['topics']['data_stream']
        mock_message.payload.decode.return_value = json.dumps(mqtt_payload)
        
        # Test with current (fixed) implementation
        initial_sizes = self.imu_buffer.get_current_buffer_size()
        self.broker.on_message(None, None, mock_message)
        final_sizes = self.imu_buffer.get_current_buffer_size()
        
        # Verify improvement
        data_processed = any(final_sizes[sensor] > initial_sizes[sensor] 
                           for sensor in final_sizes)
        
        self.assertTrue(data_processed, "Fixed implementation should process data successfully")
        self.mock_imu_logging.error.assert_not_called()
        
        print("\n" + "="*60)
        print("MQTT BROKER + IMU BUFFER INTEGRATION - AFTER FIX")
        print("="*60)
        print(f"✅ Status: WORKING")
        print(f"✅ Data processed: {data_processed}")
        print(f"✅ Buffer sizes: {final_sizes}")
        print(f"✅ No errors: {not self.mock_imu_logging.error.called}")
        print("="*60)


if __name__ == '__main__':
    unittest.main(verbosity=2)
