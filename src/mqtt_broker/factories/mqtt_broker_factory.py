from typing import Dict, Any
from ..mqtt_broker import MQTTBroker

from ..implementations.paho_mqtt_client import PahoMQTTClientAdapter
from ..abstractions.mqtt_client import MQTTClient
from ...imu_buffer import IMUBuffer


class MQTTBrokerFactory:
    """Factory for creating MQTTBroker instances with dependency injection."""
    
    @staticmethod
    def create_production_broker(config: Dict[str, Any], imu_buffer) -> MQTTBroker:
        """
        Create a production MQTTBroker with real implementations.
        
        :param config: Configuration dictionary
        :param imu_buffer: The IMU buffer instance
        :return: Configured MQTTBroker instance
        """
        # Generate unique client ID to avoid conflicts
        import uuid
        base_client_id = config['mqtt'].get('client_id', 'imu_server')
        unique_suffix = str(uuid.uuid4())[:8]
        unique_client_id = f"{base_client_id}_{unique_suffix}"
        
        # Create concrete implementations
        mqtt_client = PahoMQTTClientAdapter(unique_client_id)
        
        return MQTTBroker(
            config=config,
            mqtt_client=mqtt_client,
            imu_buffer=imu_buffer
        )
    
    @staticmethod
    def create_test_broker(
        config: Dict[str, Any],
        mqtt_client: MQTTClient = None,
        imu_buffer: IMUBuffer = None
    ) -> MQTTBroker:
        """
        Create a test MQTTBroker with injectable dependencies for testing.
        
        :param config: Configuration dictionary
        :param mqtt_client: Mock MQTT client (optional)
        :param imu_buffer: Mock IMU buffer (optional)
        :return: Configured MQTTBroker instance for testing
        """
        # Use provided mocks or create default implementations
        mqtt_client = mqtt_client or PahoMQTTClientAdapter("test_client")
        
        # For IMU buffer, we need a real adapter if none provided
        if imu_buffer is None:
            # Create a simple mock buffer for testing
            class MockIMUBuffer:
                def process_sensor_reading(self, payload):
                    pass
            imu_buffer = MockIMUBuffer()
        
        return MQTTBroker(
            config=config,
            mqtt_client=mqtt_client,
            imu_buffer=imu_buffer
        )
