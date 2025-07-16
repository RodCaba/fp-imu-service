from paho.mqtt import client as mqtt
from ..abstractions import MQTTClient
from typing import Callable

class PahoMQTTClientAdapter(MQTTClient):
    """Adapter for paho-mqtt client."""
    
    def __init__(self, client_id: str):
        self._client = mqtt.Client(client_id)
    
    def connect(self, host: str, port: int, keepalive: int) -> None:
        self._client.connect(host, port, keepalive)
    
    def disconnect(self) -> None:
        self._client.disconnect()
    
    def subscribe(self, topic: str, qos: int = 0) -> None:
        self._client.subscribe(topic, qos)
    
    def publish(self, topic: str, payload: str, qos: int = 0) -> bool:
        result = self._client.publish(topic, payload, qos)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def loop_start(self) -> None:
        self._client.loop_start()
    
    def loop_stop(self) -> None:
        self._client.loop_stop()
    
    def is_connected(self) -> bool:
        return self._client.is_connected()
    
    def set_on_connect_callback(self, callback: Callable) -> None:
        self._client.on_connect = callback
    
    def set_on_message_callback(self, callback: Callable) -> None:
        self._client.on_message = callback
    
    def set_on_disconnect_callback(self, callback: Callable) -> None:
        self._client.on_disconnect = callback
