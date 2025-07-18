from abc import ABC, abstractmethod
from typing import Callable

class MQTTClient(ABC):
    """Abstract interface for MQTT client operations."""
    
    @abstractmethod
    def connect(self, host: str, port: int, keepalive: int) -> None:
        """Connect to MQTT broker."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        pass
    
    @abstractmethod
    def reconnect(self) -> None:
        """Reconnect to MQTT broker."""
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to a topic."""
        pass
    
    @abstractmethod
    def publish(self, topic: str, payload: str, qos: int = 0) -> bool:
        """Publish a message to a topic. Returns True if successful, False otherwise."""
        pass
    
    @abstractmethod
    def loop_start(self) -> None:
        """Start the client loop."""
        pass
    
    @abstractmethod
    def loop_stop(self) -> None:
        """Stop the client loop."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if client is connected."""
        pass
    
    @abstractmethod
    def set_on_connect_callback(self, callback: Callable) -> None:
        """Set the on_connect callback."""
        pass
    
    @abstractmethod
    def set_on_message_callback(self, callback: Callable) -> None:
        """Set the on_message callback."""
        pass
    
    @abstractmethod
    def set_on_disconnect_callback(self, callback: Callable) -> None:
        """Set the on_disconnect callback."""
        pass
