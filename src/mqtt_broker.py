import paho.mqtt.client as mqtt
import json
import logging
import time
import sys
import socket
from datetime import datetime
from enum import Enum

from src.imu_buffer import IMUBuffer

class RecordingState(Enum):
    """Enumeration for the different states of recording."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"

class MQTTBroker:
  """
  A class to manage MQTT broker connections and message handling.
  """
  def __init__(self, config, imu_buffer: IMUBuffer):
    """
    Initialize the MQTT broker with configuration.
    :param config: Dictionary containing MQTT configuration parameters.
    """
    self.config = config
    self.MQTT_TOPICS = config['mqtt']['topics']
    self.client = mqtt.Client(self.config['mqtt']['client_id'])
    # Set up MQTT client callbacks
    self.client.on_connect = self.on_connect
    self.client.on_message = self.on_message
    self.client.on_disconnect = self.on_disconnect
    # Initialize state variables
    self.start_time = time.time()
    self.current_recording_state = RecordingState.IDLE
    self.service_running = False

    try:
        self.client.connect(self.config['mqtt']['broker_host'], self.config['mqtt']['broker_port'], 60)
        self.client.loop_start()
        self.service_running = True
        logging.info("Connected to MQTT broker")

    except Exception as e:
        logging.error(f"Failed to connect to MQTT broker: {str(e)}")

    self.imu_buffer = imu_buffer

    # MQTT Event Handlers
  def on_connect(self, client, userdata, flags, rc):
      """Callback for when the MQTT client connects to the broker"""
      if rc == 0:
          logging.info("Connected to MQTT broker successfully")
          
          # Subscribe to all relevant topics
          client.subscribe(self.MQTT_TOPICS['recording_control'])
          client.subscribe(self.MQTT_TOPICS['data_stream'])
          client.subscribe(self.MQTT_TOPICS['status'])

          # Publish initial status
          self.publish_status_update()

      else:
          logging.error(f"Failed to connect to MQTT broker with code {rc}")

  def on_message(self, client, userdata, msg):
      """Callback for when a message is received on a subscribed topic"""
      try:
          topic = msg.topic
          payload = json.loads(msg.payload.decode())
          
          logging.info(f"Received MQTT message on topic {topic}")
          

          if topic == self.MQTT_TOPICS['data_stream']:
              self.handle_imu_data_message(payload)
              pass
              
      except json.JSONDecodeError:
          logging.error(f"Invalid JSON in MQTT message: {msg.payload}")
      except Exception as e:
          logging.error(f"Error processing MQTT message: {str(e)}")

  def on_disconnect(self, client, userdata, rc):
      """Callback for when the MQTT client disconnects"""
      if rc != 0:
          logging.warning(f"Unexpected MQTT disconnection with code {rc}")
      else:
          logging.info("Disconnected from MQTT broker")

  def publish_status_update(self):
    """Publish current server status"""
    if self.client and self.client.is_connected():
        try:
            status = {
                'recording_state': self.current_recording_state.value,
                'timestamp': datetime.now().isoformat(),
                'service': 'imu-mqtt-service',
                'mqtt_status': 'connected',
                'uptime_seconds': time.time() - self.start_time,
            }
            result = self.client.publish(
                self.MQTT_TOPICS['status'], 
                json.dumps(status),
                qos=0
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.debug(f"Published status update")
        except Exception as e:
            logging.error(f"Error publishing status update: {str(e)}")

  def handle_imu_data_message(self, payload):
    """Handle incoming IMU data via MQTT, returns the validated payload to the next instance"""
    try:
        # Validate message structure
        device_id = payload.get('deviceId')
        imu_payload = payload.get('payload', [])
        sensor_name = payload.get('name')
        
        if not device_id:
            logging.error("IMU data message missing 'deviceId' field")
            return
            
        if not isinstance(imu_payload, list) or not imu_payload:
            logging.error("IMU data payload must be a non-empty array")
            return
        
        logging.info(f"Received IMU data from device: {device_id} (messages: {len(imu_payload)})")
        
        payload = {
            'deviceId': device_id,
            'payload': imu_payload,
            'timestamp': datetime.now().isoformat(),
            'sensor_name': sensor_name
        }

        self.imu_buffer.process_sensor_reading(payload)

    except Exception as e:
        logging.error(f"Error handling IMU data message: {str(e)}")

  def publish_recording_command(self, command):
    """Publish recording command to devices"""
    if self.client and self.client.is_connected():
        try:
            result = self.client.publish(
                self.MQTT_TOPICS['recording_control'], 
                json.dumps(command),
                qos=1
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"Published recording command: {command['command']}")
            else:
                logging.error(f"Failed to publish recording command: {result.rc}")
        except Exception as e:
            logging.error(f"Error publishing recording command: {str(e)}")

  def signal_handler(self, signum, frame):
        """Handle termination signals to gracefully shut down the service"""
        logging.info(f"Received signal {signum}. Shutting down...")
        self.service_running = False
        
        # Publish service shutdown announcement
        if self.client and self.client.is_connected():
            time.sleep(1)  # Give time for message to be sent
            self.client.loop_stop()
            self.client.disconnect()

        sys.exit(0)

  def get_ip_address(self):
    """
    Get the IP address of the device
    """
    try:
        if 'network' in self.config and 'ip' in self.config['network']:
            return self.config['network']['ip']
        # Auto-detect if not in config
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logging.error(f"Error getting IP address: {str(e)}")
        return "localhost"