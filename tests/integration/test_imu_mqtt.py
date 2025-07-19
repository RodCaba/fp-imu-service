import pytest
import json
import time
import threading
from unittest.mock import Mock, patch

from src.imu_buffer import IMUBuffer
from src.imu_message_handler import IMUMessageHandler
from fp_mqtt_broker import BrokerFactory

@pytest.fixture
def integration_config():
    """Configuration for integration tests"""
    return {
        'mqtt': {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'client_id': 'test_imu_service',
            'topics': {
                'recording_control': 'imu/recording/control',
                'data_stream': 'imu/data/stream',
                'status': 'imu/status'
            }
        },
        'data': {
            'max_buffer_size': 100
        }
    }

@pytest.fixture
def imu_buffer(integration_config):
    """Create IMU buffer for testing"""
    return IMUBuffer(integration_config)

@pytest.fixture
def imu_message_handler(imu_buffer, integration_config):
    """Create IMU message handler"""
    return IMUMessageHandler(imu_buffer, integration_config)

@pytest.mark.integration
class TestIMUMQTTIntegration:
    """Integration tests for IMU buffer and MQTT broker package"""

    def test_end_to_end_accelerometer_message_processing(self, integration_config, imu_buffer, imu_message_handler):
        """Test complete flow from MQTT message to IMU buffer for accelerometer data"""
        
        # Create broker with message handler
        broker = BrokerFactory.create_broker(integration_config, [imu_message_handler])
        
        # Simulate accelerometer MQTT message
        mqtt_payload = {
            'deviceId': 'test_device_001',
            'payload': [{
                'name': 'accelerometer',
                'values': {'x': 1.5, 'y': 2.5, 'z': 3.5}
            }],
        }
        
        # Process message through handler
        topic = integration_config['mqtt']['topics']['data_stream']
        imu_message_handler.handle_message(topic, mqtt_payload)
        
        # Verify data was stored in buffer
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 1
        assert buffer_data['accelerometer'][0]['x'] == 1.5
        assert buffer_data['accelerometer'][0]['y'] == 2.5
        assert buffer_data['accelerometer'][0]['z'] == 3.5
        
        # Verify buffer sizes
        buffer_sizes = imu_buffer.get_current_buffer_size()
        assert buffer_sizes['accelerometer'] == 1
        assert buffer_sizes['gyroscope'] == 0

    def test_end_to_end_gyroscope_message_processing(self, integration_config, imu_buffer, imu_message_handler):
        """Test complete flow for gyroscope data"""
        
        # Simulate gyroscope MQTT message
        mqtt_payload = {
            'deviceId': 'test_device_002',
            'payload': [
                {'name': 'gyroscope', 'values': {'x': -0.5, 'y': 1.2, 'z': -2.1}}
            ],
        }
        
        topic = integration_config['mqtt']['topics']['data_stream']
        imu_message_handler.handle_message(topic, mqtt_payload)
        
        # Verify data was stored correctly
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['gyroscope']) == 1
        assert buffer_data['gyroscope'][0]['x'] == -0.5
        assert buffer_data['gyroscope'][0]['y'] == 1.2
        assert buffer_data['gyroscope'][0]['z'] == -2.1

    def test_end_to_end_orientation_message_processing(self, integration_config, imu_buffer, imu_message_handler):
        """Test complete flow for orientation data with quaternions"""
        
        mqtt_payload = {
            'deviceId': 'test_device_003',
            'payload': [{
                'name': 'orientation',
                'values': {
                    'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9,
                    'roll': 10.5, 'pitch': 15.2, 'yaw': 45.7
                }
            }],
        }
        
        topic = integration_config['mqtt']['topics']['data_stream']
        imu_message_handler.handle_message(topic, mqtt_payload)
        
        # Verify orientation data
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['orientation']) == 1
        orientation = buffer_data['orientation'][0]
        assert orientation['qx'] == 0.1
        assert orientation['roll'] == 10.5
        assert orientation['yaw'] == 45.7

    def test_multiple_sensor_messages_integration(self, integration_config, imu_buffer, imu_message_handler):
        """Test processing multiple sensor types in sequence"""
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        # Send accelerometer data
        accel_payload = {
            'deviceId': 'device_multi',
            'payload': [
                {'name': 'accelerometer', 'values': {'x': 1.0, 'y': 2.0, 'z': 3.0}}
            ],
        }
        imu_message_handler.handle_message(topic, accel_payload)
        
        # Send gyroscope data
        gyro_payload = {
            'deviceId': 'device_multi',
            'payload': [
                {'name': 'gyroscope', 'values': {'x': 0.1, 'y': 0.2, 'z': 0.3}}
            ],
        }
        imu_message_handler.handle_message(topic, gyro_payload)
        
        # Send gravity data
        gravity_payload = {
            'deviceId': 'device_multi',
            'payload': [
                {'name': 'gravity', 'values': {'x': 0.0, 'y': 0.0, 'z': 9.81}}
            ],
        }
        imu_message_handler.handle_message(topic, gravity_payload)
        
        # Verify all data was processed correctly
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 1
        assert len(buffer_data['gyroscope']) == 1
        assert len(buffer_data['gravity']) == 1
        
        buffer_sizes = imu_buffer.get_current_buffer_size()
        assert buffer_sizes['accelerometer'] == 1
        assert buffer_sizes['gyroscope'] == 1
        assert buffer_sizes['gravity'] == 1

    def test_invalid_message_handling_integration(self, integration_config, imu_buffer, imu_message_handler):
        """Test integration error handling for invalid messages"""
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        # Test invalid sensor data (missing required fields)
        invalid_payload = {
            'deviceId': 'test_device',
            'payload': [
                {
                    'name': 'accelerometer',
                    'values': {'x': 1.0}
                }
            ],  # Missing y and z
        }
        
        with patch('src.imu_buffer.logging') as mock_logging:
            imu_message_handler.handle_message(topic, invalid_payload)

            # Verify error was logged
            mock_logging.error.assert_called_with("Invalid sensor reading: Missing required field: y")
        
        # Verify buffer remains empty
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 0

    def test_buffer_overflow_integration(self, integration_config, imu_buffer, imu_message_handler):
        """Test buffer overflow behavior in integration scenario"""
        
        # Set a small buffer size for testing
        integration_config['data']['max_buffer_size'] = 3
        small_buffer = IMUBuffer(integration_config)
        handler = IMUMessageHandler(small_buffer, integration_config)
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        # Send more messages than buffer size
        for i in range(5):
            payload = {
                'deviceId': f'device_{i}',
                'payload': [
                    {'name': 'accelerometer', 'values': {'x': float(i), 'y': float(i+1), 'z': float(i+2)}}
                ]
            }
            handler.handle_message(topic, payload)
        
        # Verify buffer size limit is respected
        buffer_data = small_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 3
        
        # Verify oldest data was removed (should have data from iterations 2, 3, 4)
        assert buffer_data['accelerometer'][0]['x'] == 2.0
        assert buffer_data['accelerometer'][1]['x'] == 3.0
        assert buffer_data['accelerometer'][2]['x'] == 4.0

    def test_concurrent_message_processing(self, integration_config, imu_buffer, imu_message_handler):
        """Test concurrent message processing integration"""
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        def send_accelerometer_data():
            for i in range(10):
                payload = {
                    'deviceId': f'accel_device_{i}',
                    'payload': [
                        {'name': 'accelerometer', 'values': {'x': float(i), 'y': float(i+1), 'z': float(i+2)}}
                    ]
                }
                imu_message_handler.handle_message(topic, payload)
                time.sleep(0.01)
        
        def send_gyroscope_data():
            for i in range(10):
                payload = {
                    'deviceId': f'gyro_device_{i}',
                    'payload': [
                        {'name': 'gyroscope', 'values': {'x': float(i*0.1), 'y': float((i+1)*0.1), 'z': float((i+2)*0.1)}}
                    ]
                }
                imu_message_handler.handle_message(topic, payload)
                time.sleep(0.01)
        
        # Run both threads concurrently
        thread1 = threading.Thread(target=send_accelerometer_data)
        thread2 = threading.Thread(target=send_gyroscope_data)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify both sensor types received all messages
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 10
        assert len(buffer_data['gyroscope']) == 10

    @patch('fp_mqtt_broker.broker.logging')
    def test_broker_with_imu_handler_integration(self, mock_logging, integration_config, imu_buffer):
        """Test full broker integration with IMU handler"""
        
        # Create handler and broker
        imu_handler = IMUMessageHandler(imu_buffer, integration_config)
        broker = BrokerFactory.create_broker(integration_config, [imu_handler])
        
        # Verify broker was created with handler
        assert len(broker.message_handlers) == 1
        assert isinstance(broker.message_handlers[0], IMUMessageHandler)
        
        # Verify subscribed topics
        expected_topic = integration_config['mqtt']['topics']['data_stream']
        assert expected_topic in broker.subscribed_topics
        
        # Simulate message reception through broker
        mock_msg = Mock()
        mock_msg.topic = expected_topic
        mock_msg.payload.decode.return_value = json.dumps({
            'deviceId': 'integration_test',
            'payload': [
                {'name': 'accelerometer', 'values': {'x': 5.5, 'y': 6.6, 'z': 7.7}}
            ]
        })
        
        # Process message through broker
        broker.on_message(None, None, mock_msg)
        
        # Verify data reached IMU buffer
        buffer_data = imu_buffer.get_data()
        assert len(buffer_data['accelerometer']) == 1
        assert buffer_data['accelerometer'][0]['x'] == 5.5

    def test_message_validation_integration(self, integration_config, imu_buffer, imu_message_handler):
        """Test message validation in integration context"""
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        # Test various invalid message formats
        invalid_messages = [
            # Missing payload
            {'deviceId': 'test'},
            # Invalid payload type
            {'deviceId': 'test', 'payload': 'invalid'},
            # Payload is object instead of array
            {'deviceId': 'test', 'payload': {'name': 'accelerometer', 'values': {'x': 1, 'y': 2, 'z': 3}}},
            # Empty payload array
            {'deviceId': 'test', 'payload': []},
            # Missing sensor name
            {'deviceId': 'test', 'payload': [{'values': {'x': 1, 'y': 2, 'z': 3}}]},
        ]
        

        for invalid_msg in invalid_messages:
            with pytest.raises(RuntimeError):
                imu_message_handler.handle_message(topic, invalid_msg)
        
        # Verify buffer remains empty after all invalid messages
        buffer_data = imu_buffer.get_data()
        assert all(len(sensor_data) == 0 for sensor_data in buffer_data.values())

    def test_sensor_type_routing_integration(self, integration_config, imu_buffer, imu_message_handler):
        """Test that different sensor types are routed correctly"""
        
        topic = integration_config['mqtt']['topics']['data_stream']
        
        # Test all supported sensor types
        sensor_tests = [
            ({'name': 'accelerometer', 'values': {'x': 1.0, 'y': 1.1, 'z': 1.2}}),
            ({'name': 'gyroscope', 'values': {'x': 2.0, 'y': 2.1, 'z': 2.2}}),
            ({'name': 'gravity', 'values': {'x': 3.0, 'y': 3.1, 'z': 3.2}}),
            ({'name': 'totalacceleration', 'values': {'x': 4.0, 'y': 4.1, 'z': 4.2}}),
            ({'name': 'orientation', 'values': {'qx': 0.1, 'qy': 0.2, 'qz': 0.3, 'qw': 0.9, 'roll': 5.0, 'pitch': 6.0, 'yaw': 7.0}})
        ]
        
        for sensor_data in sensor_tests:
            payload = {
                'deviceId': 'test_id',
                'payload': [sensor_data],
            }
            imu_message_handler.handle_message(topic, payload)
        
        # Verify each sensor type has data in correct buffer
        buffer_data = imu_buffer.get_data()
        buffer_sizes = imu_buffer.get_current_buffer_size()
        
        assert buffer_sizes['accelerometer'] == 1
        assert buffer_sizes['gyroscope'] == 1
        assert buffer_sizes['gravity'] == 1
        assert buffer_sizes['total_acceleration'] == 1
        assert buffer_sizes['orientation'] == 1
        
        # Verify specific data values
        assert buffer_data['accelerometer'][0]['x'] == 1.0
        assert buffer_data['gyroscope'][0]['y'] == 2.1
        assert buffer_data['orientation'][0]['roll'] == 5.0
