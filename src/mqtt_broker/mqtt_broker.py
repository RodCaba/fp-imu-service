import json
import time
import logging
import sys
import socket
from datetime import datetime
from enum import Enum
from typing import Dict, Any

from .abstractions.mqtt_client import MQTTClient
from ..imu_buffer import IMUBuffer


class RecordingState(Enum):
    """Enumeration for the different states of recording."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"

class MQTTBroker:
  """
  A class to manage MQTT broker connections and message handling.
  """
  def __init__(self, 
               config: Dict[str, Any], 
               mqtt_client: MQTTClient,
               imu_buffer: IMUBuffer):
    """
    Initialize the MQTT broker with configuration and dependencies.
    :param config: Dictionary containing MQTT configuration parameters.
    :param mqtt_client: MQTT client abstraction
    :param imu_buffer: IMU buffer abstraction
    """
    self.config = config
    self.MQTT_TOPICS = config['mqtt']['topics']
    self.client = mqtt_client
    self.imu_buffer = imu_buffer
    
    # Set up MQTT client callbacks
    self.client.set_on_connect_callback(self.on_connect)
    self.client.set_on_message_callback(self.on_message)
    self.client.set_on_disconnect_callback(self.on_disconnect)
    
    # Initialize state variables
    self.start_time = time.time()
    self.current_recording_state = RecordingState.IDLE
    self.service_running = False
    self.connection_established = False

    try:
        logging.info(f"Attempting to connect to MQTT broker at {self.config['mqtt']['broker_host']}:{self.config['mqtt']['broker_port']}")
        self.client.connect(self.config['mqtt']['broker_host'], self.config['mqtt']['broker_port'], 60)
        self.client.loop_start()
        
        # Wait for connection to be established (with timeout)
        connection_timeout = 10  # seconds
        connection_start_time = time.time()
        
        while not self.connection_established and (time.time() - connection_start_time) < connection_timeout:
            time.sleep(0.1)
        
        if self.connection_established:
            self.service_running = True
            logging.info("MQTT broker service started successfully")
        else:
            logging.error("Failed to establish MQTT connection within timeout period")
            self.client.loop_stop()

    except Exception as e:
        logging.error(f"Failed to connect to MQTT broker: {str(e)}")
        self.service_running = False

    # MQTT Event Handlers
  def on_connect(self, client, userdata, flags, rc):
      """Callback for when the MQTT client connects to the broker"""
      if rc == 0:
          logging.info("Connected to MQTT broker successfully")
          self.connection_established = True

          # Subscribe to all relevant topics
          self.client.subscribe(self.MQTT_TOPICS['recording_control'])
          self.client.subscribe(self.MQTT_TOPICS['data_stream'])
          self.client.subscribe(self.MQTT_TOPICS['status'])

          # Publish initial status
          self.publish_status_update()

      else:
          logging.error(f"Failed to connect to MQTT broker with code {rc}")
          self.connection_established = False

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
      self.connection_established = False
      
      if rc != 0:
          logging.warning(f"Unexpected MQTT disconnection with code {rc}")
          # Attempt to reconnect automatically
          self._attempt_reconnection()
      else:
          logging.info("Disconnected from MQTT broker")

  def _attempt_reconnection(self):
      """Attempt to reconnect to the MQTT broker"""
      if self.service_running:
          try:
              logging.info("Attempting to reconnect to MQTT broker...")
              self.client.reconnect()
          except Exception as e:
              logging.error(f"Failed to reconnect to MQTT broker: {str(e)}")
              # Don't set service_running to False here, let the timeout logic handle it

  def publish_status_update(self):
    """Publish current server status"""
    if self.client and self.client.is_connected() and self.connection_established:
        try:
            status = {
                'recording_state': self.current_recording_state.value,
                'timestamp': datetime.now().isoformat(),
                'service': 'imu-mqtt-service',
                'mqtt_status': 'connected',
                'uptime_seconds': time.time() - self.start_time,
            }
            success = self.client.publish(
                self.MQTT_TOPICS['status'], 
                json.dumps(status),
                qos=0
            )
            if success:
                logging.debug(f"Published status update")
            else:
                logging.warning("Failed to publish status update")
        except Exception as e:
            logging.error(f"Error publishing status update: {str(e)}")
    else:
        logging.debug("Skipping status update - MQTT client not properly connected")

  def handle_imu_data_message(self, payload):
    """Handle incoming IMU data via MQTT, returns the validated payload to the next instance"""
    try:
        # Validate message structure
        device_id = payload.get('deviceId')
        imu_payload = payload.get('payload', [])
        
        if not device_id:
            logging.error("IMU data message missing 'deviceId' field")
            return
            
        if not isinstance(imu_payload, list) or not imu_payload:
            logging.error("IMU data payload must be a non-empty array")
            return

        logging.info(f"Received IMU data from device: {device_id}, data points: {len(imu_payload)})")

        # Process each data point in the payload individually
        for sensor_data in imu_payload:
            if isinstance(sensor_data, dict):
                sensor_name = sensor_data.get('name', 'unknown')
                data = sensor_data.get('values', {})
                # Format the data for the IMU buffer (individual sensor reading)
                formatted_reading = {
                    'sensor_name': sensor_name,
                    'payload': data
                }
                logging.info(f"Processing IMU data for sensor: {sensor_name}, data: {data}")
                self.imu_buffer.process_sensor_reading(formatted_reading)
            else:
                logging.warning(f"Skipping invalid sensor data point from device {device_id}: {sensor_data}")

    except Exception as e:
        logging.error(f"Error handling IMU data message: {str(e)}")

  def publish_recording_command(self, command):
    """Publish recording command to devices"""
    if self.client and self.client.is_connected():
        try:
            success = self.client.publish(
                self.MQTT_TOPICS['recording_control'], 
                json.dumps(command),
                qos=1
            )
            if success:
                logging.info(f"Published recording command: {command['command']}")
            else:
                logging.error(f"Failed to publish recording command")
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