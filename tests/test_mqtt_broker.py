import unittest
from unittest.mock import Mock, patch, call
import json

from src.mqtt_broker.mqtt_broker import MQTTBroker, RecordingState


class TestMQTTBroker(unittest.TestCase):
    """Test cases for the MQTTBroker class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            'mqtt': {
                'topics': {
                    'recording_control': 'test/recording',
                    'data_stream': 'test/data',
                    'status': 'test/status'
                },
                'broker_host': 'localhost',
                'broker_port': 1883,
                'client_id': 'test_client'
            }
        }
        
        # Create mock dependencies
        self.mock_mqtt_client = Mock()
        self.mock_imu_buffer = Mock()
        
        # Configure mock behaviors
        self.mock_mqtt_client.is_connected.return_value = True
        self.mock_mqtt_client.publish.return_value = True
        
        # Set up patches for external modules
        self.patcher_logging = patch('src.mqtt_broker.mqtt_broker.logging')
        self.patcher_time = patch('src.mqtt_broker.mqtt_broker.time')
        self.patcher_datetime = patch('src.mqtt_broker.mqtt_broker.datetime')
        self.patcher_socket = patch('src.mqtt_broker.mqtt_broker.socket')
        self.patcher_sys = patch('src.mqtt_broker.mqtt_broker.sys')
        
        # Start patches and store mock objects
        self.mock_logging = self.patcher_logging.start()
        self.mock_time = self.patcher_time.start()
        self.mock_datetime = self.patcher_datetime.start()
        self.mock_socket = self.patcher_socket.start()
        self.mock_sys = self.patcher_sys.start()
        
        # Configure common mock behaviors
        self.mock_time.time.return_value = 1000.0
        self.mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        
        # Configure socket mocks
        self.mock_socket_instance = Mock()
        self.mock_socket.socket.return_value = self.mock_socket_instance
        self.mock_socket.AF_INET = 2
        self.mock_socket.SOCK_DGRAM = 2
        self.mock_socket_instance.getsockname.return_value = ("192.168.1.100", 12345)
        
    def tearDown(self):
        """Clean up patches after each test method."""
        self.patcher_logging.stop()
        self.patcher_time.stop()
        self.patcher_datetime.stop()
        self.patcher_socket.stop()
        self.patcher_sys.stop()
        
    def create_broker(self, connect_success=True):
        """Create a MQTTBroker instance with mocked dependencies."""
        if not connect_success:
            self.mock_mqtt_client.connect.side_effect = Exception("Connection failed")
        
        return MQTTBroker(
            config=self.config,
            mqtt_client=self.mock_mqtt_client,
            imu_buffer=self.mock_imu_buffer
        )
    
    def test_broker_initialization_success(self):
        """Test successful broker initialization."""
        broker = self.create_broker()
        
        # Verify initial state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        self.assertTrue(broker.service_running)
        self.assertEqual(broker.start_time, 1000.0)
        
        # Verify MQTT client was configured
        self.mock_mqtt_client.set_on_connect_callback.assert_called_once()
        self.mock_mqtt_client.set_on_message_callback.assert_called_once()
        self.mock_mqtt_client.set_on_disconnect_callback.assert_called_once()
        
        # Verify connection attempt
        self.mock_mqtt_client.connect.assert_called_once_with('localhost', 1883, 60)
        self.mock_mqtt_client.loop_start.assert_called_once()
    
    def test_broker_initialization_failure(self):
        """Test broker initialization when connection fails."""
        broker = self.create_broker(connect_success=False)
        
        # Verify failure state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        self.assertFalse(broker.service_running)
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("Failed to connect to MQTT broker: Connection failed")
    
    def test_on_connect_success(self):
        """Test successful MQTT connection callback."""
        broker = self.create_broker()
        
        # Call the callback with success code
        broker.on_connect(None, None, None, 0)
        
        # Verify subscriptions
        expected_calls = [
            call('test/recording'),
            call('test/data'),
            call('test/status')
        ]
        self.mock_mqtt_client.subscribe.assert_has_calls(expected_calls)
        
        # Verify status publish was called
        self.mock_mqtt_client.publish.assert_called()
        
        # Verify success logging
        self.mock_logging.info.assert_called_with("Connected to MQTT broker successfully")
    
    def test_on_connect_failure(self):
        """Test failed MQTT connection callback."""
        broker = self.create_broker()
        
        # Call the callback with failure code
        broker.on_connect(None, None, None, 1)
        
        # Verify no subscriptions
        self.mock_mqtt_client.subscribe.assert_not_called()
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("Failed to connect to MQTT broker with code 1")
    
    def test_on_message_valid_imu_data(self):
        """Test handling valid IMU data message."""
        broker = self.create_broker()
        
        # Create mock message
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = json.dumps({
            'deviceId': 'test_device',
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        })
        
        # Call the callback
        broker.on_message(None, None, mock_msg)
        
        # Verify message processing
        self.mock_logging.info.assert_any_call("Received MQTT message on topic test/data")
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
    
    def test_on_message_invalid_json(self):
        """Test handling message with invalid JSON."""
        broker = self.create_broker()
        
        # Create mock message with invalid JSON
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = "invalid json"
        mock_msg.payload = b"invalid json"
        
        # Call the callback
        broker.on_message(None, None, mock_msg)
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("Invalid JSON in MQTT message: b'invalid json'")
    
    def test_on_disconnect_unexpected(self):
        """Test unexpected disconnection callback."""
        broker = self.create_broker()
        
        # Call the callback with non-zero code (unexpected)
        broker.on_disconnect(None, None, 1)
        
        # Verify warning logging
        self.mock_logging.warning.assert_called_with("Unexpected MQTT disconnection with code 1")
    
    def test_on_disconnect_expected(self):
        """Test expected disconnection callback."""
        broker = self.create_broker()
        
        # Call the callback with zero code (expected)
        broker.on_disconnect(None, None, 0)
        
        # Verify info logging
        self.mock_logging.info.assert_called_with("Disconnected from MQTT broker")
    
    def test_publish_status_update_success(self):
        """Test successful status update publishing."""
        # Configure time mocks for this test
        self.mock_time.time.return_value = 2000.0
        
        broker = self.create_broker()
        broker.start_time = 1000.0  # Set start time
        
        # Call the method
        broker.publish_status_update()
        
        # Verify publish was called
        self.mock_mqtt_client.publish.assert_called()
        call_args = self.mock_mqtt_client.publish.call_args
        
        # Check topic
        self.assertEqual(call_args[0][0], 'test/status')
        
        # Check QoS
        self.assertEqual(call_args[1]['qos'], 0)
        
        # Check payload structure
        payload = json.loads(call_args[0][1])
        self.assertIn('recording_state', payload)
        self.assertIn('timestamp', payload)
        self.assertIn('service', payload)
        self.assertEqual(payload['recording_state'], 'idle')
        self.assertEqual(payload['service'], 'imu-mqtt-service')
        self.assertEqual(payload['uptime_seconds'], 1000.0)  # 2000 - 1000
        
        # Verify success logging
        self.mock_logging.debug.assert_called_with("Published status update")
    
    def test_publish_status_update_failure(self):
        """Test status update publishing failure."""
        broker = self.create_broker()
        self.mock_mqtt_client.publish.return_value = False
        
        # Call the method
        broker.publish_status_update()
        
        # Verify warning logging
        self.mock_logging.warning.assert_called_with("Failed to publish status update")
    
    def test_publish_status_update_not_connected(self):
        """Test status update when not connected."""
        broker = self.create_broker()
        self.mock_mqtt_client.is_connected.return_value = False
        
        # Call the method
        broker.publish_status_update()
        
        # Verify publish was not called
        self.mock_mqtt_client.publish.assert_not_called()
    
    def test_handle_imu_data_message_valid(self):
        """Test handling valid IMU data message."""
        broker = self.create_broker()
        
        payload = {
            'deviceId': 'test_device',
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify IMU buffer was called once for each data point
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
        
        # Get the processed payload (now in IMU buffer format)
        processed_payload = self.mock_imu_buffer.process_sensor_reading.call_args[0][0]
        self.assertEqual(processed_payload['sensor_name'], 'accelerometer')
        self.assertEqual(processed_payload['payload'], {'x': 1.0, 'y': 2.0, 'z': 3.0})
        
        # Verify info logging with updated message format
        self.mock_logging.info.assert_called_with("Received IMU data from device: test_device (sensor: accelerometer, data points: 1)")
    
    def test_handle_imu_data_message_missing_device_id(self):
        """Test handling IMU data message without device ID."""
        broker = self.create_broker()
        
        payload = {
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("IMU data message missing 'deviceId' field")
        
        # Verify IMU buffer was not called
        self.mock_imu_buffer.process_sensor_reading.assert_not_called()
    
    def test_handle_imu_data_message_empty_payload(self):
        """Test handling IMU data message with empty payload."""
        broker = self.create_broker()
        
        payload = {
            'deviceId': 'test_device',
            'payload': [],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("IMU data payload must be a non-empty array")
        
        # Verify IMU buffer was not called
        self.mock_imu_buffer.process_sensor_reading.assert_not_called()
    
    def test_publish_recording_command_success(self):
        """Test successful recording command publishing."""
        broker = self.create_broker()
        
        command = {'command': 'start', 'device_id': 'test_device'}
        
        # Call the method
        broker.publish_recording_command(command)
        
        # Verify publish was called
        self.mock_mqtt_client.publish.assert_called()
        call_args = self.mock_mqtt_client.publish.call_args
        
        # Check topic and QoS
        self.assertEqual(call_args[0][0], 'test/recording')
        self.assertEqual(call_args[1]['qos'], 1)
        
        # Check payload
        payload = json.loads(call_args[0][1])
        self.assertEqual(payload['command'], 'start')
        
        # Verify success logging
        self.mock_logging.info.assert_called_with("Published recording command: start")
    
    def test_publish_recording_command_failure(self):
        """Test recording command publishing failure."""
        broker = self.create_broker()
        self.mock_mqtt_client.publish.return_value = False
        
        command = {'command': 'start', 'device_id': 'test_device'}
        
        # Call the method
        broker.publish_recording_command(command)
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("Failed to publish recording command")
    
    def test_signal_handler(self):
        """Test signal handler for graceful shutdown."""
        broker = self.create_broker()
        
        # Call the signal handler
        broker.signal_handler(2, None)
        
        # Verify shutdown sequence
        self.assertFalse(broker.service_running)
        self.mock_time.sleep.assert_called_with(1)
        self.mock_mqtt_client.loop_stop.assert_called_once()
        self.mock_mqtt_client.disconnect.assert_called_once()
        self.mock_sys.exit.assert_called_with(0)
        
        # Verify shutdown logging
        self.mock_logging.info.assert_called_with("Received signal 2. Shutting down...")
    
    def test_get_ip_address_success(self):
        """Test successful IP address retrieval using socket auto-detection."""
        broker = self.create_broker()
        
        # Call the method
        result = broker.get_ip_address()
        
        # Verify result
        self.assertEqual(result, "192.168.1.100")
        
        # Verify socket operations
        self.mock_socket.socket.assert_called_with(2, 2)  # AF_INET, SOCK_DGRAM
        self.mock_socket_instance.connect.assert_called_with(("8.8.8.8", 80))
        self.mock_socket_instance.close.assert_called_once()
    
    def test_get_ip_address_with_config(self):
        """Test IP address retrieval when specified in config."""
        broker = self.create_broker()
        broker.config['network'] = {'ip': '10.0.0.1'}
        
        # Call the method
        result = broker.get_ip_address()
        
        # Verify result from config
        self.assertEqual(result, "10.0.0.1")
        
        # Verify socket operations were not called
        self.mock_socket.socket.assert_not_called()
    
    def test_get_ip_address_failure(self):
        """Test IP address retrieval failure."""
        broker = self.create_broker()
        
        # Mock socket to raise exception
        self.mock_socket.socket.side_effect = Exception("Network error")
        
        # Call the method
        result = broker.get_ip_address()
        
        # Verify fallback
        self.assertEqual(result, "localhost")
        
        # Verify error logging
        self.mock_logging.error.assert_called_with("Error getting IP address: Network error")
    
    def test_recording_state_transitions(self):
        """Test recording state management."""
        broker = self.create_broker()
        
        # Test initial state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        
        # Test state change
        broker.current_recording_state = RecordingState.RECORDING
        self.assertEqual(broker.current_recording_state, RecordingState.RECORDING)


class TestMQTTBrokerIntegration(unittest.TestCase):
    """Integration tests that test multiple components working together."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'mqtt': {
                'topics': {
                    'recording_control': 'test/recording',
                    'data_stream': 'test/data',
                    'status': 'test/status'
                },
                'broker_host': 'localhost',
                'broker_port': 1883,
                'client_id': 'test_client'
            }
        }
        
        # Create mock dependencies
        self.mock_mqtt_client = Mock()
        self.mock_imu_buffer = Mock()
        
        # Configure mock behaviors
        self.mock_mqtt_client.is_connected.return_value = True
        self.mock_mqtt_client.publish.return_value = True
    
    @patch('src.mqtt_broker.mqtt_broker.logging')
    def test_full_message_processing_flow(self, mock_logging):
        """Test the complete flow from receiving a message to processing it."""
        broker = MQTTBroker(
            config=self.config,
            mqtt_client=self.mock_mqtt_client,
            imu_buffer=self.mock_imu_buffer
        )
        
        # Simulate connection success
        broker.on_connect(None, None, None, 0)
        
        # Simulate receiving an IMU data message
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = json.dumps({
            'deviceId': 'sensor_001',
            'payload': [
                {'x': 1.5, 'y': 2.5, 'z': 3.5, 'timestamp': 1000},
                {'x': 1.6, 'y': 2.6, 'z': 3.6, 'timestamp': 1001}
            ],
            'name': 'accelerometer'
        })
        
        broker.on_message(None, None, mock_msg)
        
        # Verify the complete flow
        # 1. Connection successful and subscriptions made
        self.assertEqual(self.mock_mqtt_client.subscribe.call_count, 3)
        
        # 2. Message was processed
        mock_logging.info.assert_any_call("Received MQTT message on topic test/data")
        mock_logging.info.assert_any_call("Received IMU data from device: sensor_001 (messages: 2)")
        
        # 3. IMU buffer was called with processed data
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
        processed_data = self.mock_imu_buffer.process_sensor_reading.call_args[0][0]
        self.assertEqual(processed_data['deviceId'], 'sensor_001')
        self.assertEqual(processed_data['sensor_name'], 'accelerometer')
        self.assertEqual(len(processed_data['payload']), 2)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
    
    def test_broker_initialization_success(self):
        """Test successful broker initialization."""
        broker = self.create_broker()
        
        # Verify initial state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        self.assertTrue(broker.service_running)
        self.assertEqual(broker.start_time, 1000.0)
        
        # Verify MQTT client was configured
        self.mock_mqtt_client.set_on_connect_callback.assert_called_once()
        self.mock_mqtt_client.set_on_message_callback.assert_called_once()
        self.mock_mqtt_client.set_on_disconnect_callback.assert_called_once()
        
        # Verify connection attempt
        self.mock_mqtt_client.connect.assert_called_once_with('localhost', 1883, 60)
        self.mock_mqtt_client.loop_start.assert_called_once()
        
        # Verify success logging
        self.mock_logger.info.assert_called_with("Connected to MQTT broker")
    
    def test_broker_initialization_failure(self):
        """Test broker initialization when connection fails."""
        broker = self.create_broker(connect_success=False)
        
        # Verify failure state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        self.assertFalse(broker.service_running)
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("Failed to connect to MQTT broker: Connection failed")
    
    def test_on_connect_success(self):
        """Test successful MQTT connection callback."""
        broker = self.create_broker()
        
        # Call the callback with success code
        broker.on_connect(None, None, None, 0)
        
        # Verify subscriptions
        expected_calls = [
            call('test/recording'),
            call('test/data'),
            call('test/status')
        ]
        self.mock_mqtt_client.subscribe.assert_has_calls(expected_calls)
        
        # Verify status publish was called
        self.mock_mqtt_client.publish.assert_called()
        
        # Verify success logging
        self.mock_logger.info.assert_called_with("Connected to MQTT broker successfully")
    
    def test_on_connect_failure(self):
        """Test failed MQTT connection callback."""
        broker = self.create_broker()
        
        # Call the callback with failure code
        broker.on_connect(None, None, None, 1)
        
        # Verify no subscriptions
        self.mock_mqtt_client.subscribe.assert_not_called()
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("Failed to connect to MQTT broker with code 1")
    
    def test_on_message_valid_imu_data(self):
        """Test handling valid IMU data message."""
        broker = self.create_broker()
        
        # Create mock message
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = json.dumps({
            'deviceId': 'test_device',
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        })
        
        # Call the callback
        broker.on_message(None, None, mock_msg)
        
        # Verify message processing
        self.mock_logger.info.assert_called_with("Received MQTT message on topic test/data")
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
    
    def test_on_message_invalid_json(self):
        """Test handling message with invalid JSON."""
        broker = self.create_broker()
        
        # Create mock message with invalid JSON
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = "invalid json"
        mock_msg.payload = b"invalid json"
        
        # Call the callback
        broker.on_message(None, None, mock_msg)
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("Invalid JSON in MQTT message: b'invalid json'")
    
    def test_on_disconnect_unexpected(self):
        """Test unexpected disconnection callback."""
        broker = self.create_broker()
        
        # Call the callback with non-zero code (unexpected)
        broker.on_disconnect(None, None, 1)
        
        # Verify warning logging
        self.mock_logger.warning.assert_called_with("Unexpected MQTT disconnection with code 1")
    
    def test_on_disconnect_expected(self):
        """Test expected disconnection callback."""
        broker = self.create_broker()
        
        # Call the callback with zero code (expected)
        broker.on_disconnect(None, None, 0)
        
        # Verify info logging
        self.mock_logger.info.assert_called_with("Disconnected from MQTT broker")
    
    def test_publish_status_update_success(self):
        """Test successful status update publishing."""
        broker = self.create_broker()
        
        # Call the method
        broker.publish_status_update()
        
        # Verify publish was called
        self.mock_mqtt_client.publish.assert_called()
        call_args = self.mock_mqtt_client.publish.call_args
        
        # Check topic
        self.assertEqual(call_args[0][0], 'test/status')
        
        # Check QoS
        self.assertEqual(call_args[1]['qos'], 0)
        
        # Check payload structure
        payload = json.loads(call_args[0][1])
        self.assertIn('recording_state', payload)
        self.assertIn('timestamp', payload)
        self.assertIn('service', payload)
        self.assertEqual(payload['recording_state'], 'idle')
        self.assertEqual(payload['service'], 'imu-mqtt-service')
        
        # Verify success logging
        self.mock_logger.debug.assert_called_with("Published status update")
    
    def test_publish_status_update_failure(self):
        """Test status update publishing failure."""
        broker = self.create_broker()
        self.mock_mqtt_client.publish.return_value = False
        
        # Call the method
        broker.publish_status_update()
        
        # Verify warning logging
        self.mock_logger.warning.assert_called_with("Failed to publish status update")
    
    def test_publish_status_update_not_connected(self):
        """Test status update when not connected."""
        broker = self.create_broker()
        self.mock_mqtt_client.is_connected.return_value = False
        
        # Call the method
        broker.publish_status_update()
        
        # Verify publish was not called
        self.mock_mqtt_client.publish.assert_not_called()
    
    def test_handle_imu_data_message_valid(self):
        """Test handling valid IMU data message."""
        broker = self.create_broker()
        
        payload = {
            'deviceId': 'test_device',
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify IMU buffer was called
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
        
        # Get the processed payload
        processed_payload = self.mock_imu_buffer.process_sensor_reading.call_args[0][0]
        self.assertEqual(processed_payload['deviceId'], 'test_device')
        self.assertEqual(processed_payload['sensor_name'], 'accelerometer')
        self.assertIn('timestamp', processed_payload)
        
        # Verify info logging
        self.mock_logger.info.assert_called_with("Received IMU data from device: test_device (messages: 1)")
    
    def test_handle_imu_data_message_missing_device_id(self):
        """Test handling IMU data message without device ID."""
        broker = self.create_broker()
        
        payload = {
            'payload': [{'x': 1.0, 'y': 2.0, 'z': 3.0}],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("IMU data message missing 'deviceId' field")
        
        # Verify IMU buffer was not called
        self.mock_imu_buffer.process_sensor_reading.assert_not_called()
    
    def test_handle_imu_data_message_empty_payload(self):
        """Test handling IMU data message with empty payload."""
        broker = self.create_broker()
        
        payload = {
            'deviceId': 'test_device',
            'payload': [],
            'name': 'accelerometer'
        }
        
        # Call the method
        broker.handle_imu_data_message(payload)
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("IMU data payload must be a non-empty array")
        
        # Verify IMU buffer was not called
        self.mock_imu_buffer.process_sensor_reading.assert_not_called()
    
    def test_publish_recording_command_success(self):
        """Test successful recording command publishing."""
        broker = self.create_broker()
        
        command = {'command': 'start', 'device_id': 'test_device'}
        
        # Call the method
        broker.publish_recording_command(command)
        
        # Verify publish was called
        self.mock_mqtt_client.publish.assert_called()
        call_args = self.mock_mqtt_client.publish.call_args
        
        # Check topic and QoS
        self.assertEqual(call_args[0][0], 'test/recording')
        self.assertEqual(call_args[1]['qos'], 1)
        
        # Check payload
        payload = json.loads(call_args[0][1])
        self.assertEqual(payload['command'], 'start')
        
        # Verify success logging
        self.mock_logger.info.assert_called_with("Published recording command: start")
    
    def test_publish_recording_command_failure(self):
        """Test recording command publishing failure."""
        broker = self.create_broker()
        self.mock_mqtt_client.publish.return_value = False
        
        command = {'command': 'start', 'device_id': 'test_device'}
        
        # Call the method
        broker.publish_recording_command(command)
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("Failed to publish recording command")
    
    def test_signal_handler(self):
        """Test signal handler for graceful shutdown."""
        broker = self.create_broker()
        
        # Call the signal handler
        broker.signal_handler(2, None)
        
        # Verify shutdown sequence
        self.assertFalse(broker.service_running)
        self.mock_time_provider.sleep.assert_called_with(1)
        self.mock_mqtt_client.loop_stop.assert_called_once()
        self.mock_mqtt_client.disconnect.assert_called_once()
        self.mock_system_provider.exit.assert_called_with(0)
        
        # Verify shutdown logging
        self.mock_logger.info.assert_called_with("Received signal 2. Shutting down...")
    
    def test_get_ip_address_success(self):
        """Test successful IP address retrieval."""
        broker = self.create_broker()
        
        # Call the method
        result = broker.get_ip_address()
        
        # Verify result
        self.assertEqual(result, "192.168.1.100")
        self.mock_network_provider.get_ip_address.assert_called_once_with(self.config)
    
    def test_get_ip_address_failure(self):
        """Test IP address retrieval failure."""
        broker = self.create_broker()
        self.mock_network_provider.get_ip_address.side_effect = Exception("Network error")
        
        # Call the method
        result = broker.get_ip_address()
        
        # Verify fallback
        self.assertEqual(result, "localhost")
        
        # Verify error logging
        self.mock_logger.error.assert_called_with("Error getting IP address: Network error")
    
    def test_recording_state_transitions(self):
        """Test recording state management."""
        broker = self.create_broker()
        
        # Test initial state
        self.assertEqual(broker.current_recording_state, RecordingState.IDLE)
        
        # Test state change
        broker.current_recording_state = RecordingState.RECORDING
        self.assertEqual(broker.current_recording_state, RecordingState.RECORDING)
        
        # Test state in status update
        broker.publish_status_update()
        call_args = self.mock_mqtt_client.publish.call_args
        payload = json.loads(call_args[0][1])
        self.assertEqual(payload['recording_state'], 'recording')


class TestMQTTBrokerIntegration(unittest.TestCase):
    """Integration tests that test multiple components working together."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'mqtt': {
                'topics': {
                    'recording_control': 'test/recording',
                    'data_stream': 'test/data',
                    'status': 'test/status'
                },
                'broker_host': 'localhost',
                'broker_port': 1883,
                'client_id': 'test_client'
            }
        }
        
        # Create mock dependencies
        self.mock_mqtt_client = Mock()
        self.mock_time_provider = Mock()
        self.mock_network_provider = Mock()
        self.mock_logger = Mock()
        self.mock_system_provider = Mock()
        self.mock_imu_buffer = Mock()
        
        # Configure mock behaviors
        self.mock_mqtt_client.is_connected.return_value = True
        self.mock_mqtt_client.publish.return_value = True
    
    @patch('src.mqtt_broker.mqtt_broker.logging')
    def test_full_message_processing_flow(self, mock_logging):
        """Test the complete flow from receiving a message to processing it."""
        broker = MQTTBroker(
            config=self.config,
            mqtt_client=self.mock_mqtt_client,
            imu_buffer=self.mock_imu_buffer
        )
        
        # Simulate connection success
        broker.on_connect(None, None, None, 0)
        
        # Simulate receiving an IMU data message
        mock_msg = Mock()
        mock_msg.topic = 'test/data'
        mock_msg.payload.decode.return_value = json.dumps({
            'deviceId': 'sensor_001',
            'payload': [
                {'x': 1.5, 'y': 2.5, 'z': 3.5, 'timestamp': 1000},
                {'x': 1.6, 'y': 2.6, 'z': 3.6, 'timestamp': 1001}
            ],
            'name': 'accelerometer'
        })
        
        broker.on_message(None, None, mock_msg)
        
        # Verify the complete flow
        # 1. Connection successful and subscriptions made
        self.assertEqual(self.mock_mqtt_client.subscribe.call_count, 3)
        
        # 2. Message was processed
        mock_logging.info.assert_any_call("Received MQTT message on topic test/data")
        mock_logging.info.assert_any_call("Received IMU data from device: sensor_001 (messages: 2)")
        
        # 3. IMU buffer was called with processed data
        self.mock_imu_buffer.process_sensor_reading.assert_called_once()
        processed_data = self.mock_imu_buffer.process_sensor_reading.call_args[0][0]
        self.assertEqual(processed_data['deviceId'], 'sensor_001')
        self.assertEqual(processed_data['sensor_name'], 'accelerometer')
        self.assertEqual(len(processed_data['payload']), 2)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
