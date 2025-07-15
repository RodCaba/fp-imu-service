import json
import logging
from datetime import datetime
import paho.mqtt.client as mqtt
import threading
import time
import signal
import sys
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('imu_server.log'),
        logging.StreamHandler()
    ]
)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Recording states
class RecordingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"

# Global state
current_recording_state = RecordingState.IDLE
active_recording_sessions = set()  # Track active recording sessions
service_running = True

# In-memory buffer to store IMU data
accelerometer_data_buffer = []
gyroscope_data_buffer = []
gravity_data_buffer = []
total_acceleration_data_buffer = []
orientation_data_buffer = []
MAX_BUFFER_SIZE = config['data']['max_buffer_size']

# MQTT Configuration
MQTT_TOPICS = config['mqtt']['topics']
mqtt_client = None

# MQTT Event Handlers
def on_connect(client, userdata, flags, rc):
    """Callback for when the MQTT client connects to the broker"""
    if rc == 0:
        logging.info("Connected to MQTT broker successfully")
        
        # Subscribe to all relevant topics
        client.subscribe(MQTT_TOPICS['recording_control'])
        client.subscribe(MQTT_TOPICS['data_stream'])
        client.subscribe(MQTT_TOPICS['status'])
        
        # Publish initial status
        publish_status_update()
        
    else:
        logging.error(f"Failed to connect to MQTT broker with code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received on a subscribed topic"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        logging.info(f"Received MQTT message on topic {topic}")
        

        if topic == MQTT_TOPICS['data_stream']:
            handle_imu_data_message(payload)
            pass
            
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in MQTT message: {msg.payload}")
    except Exception as e:
        logging.error(f"Error processing MQTT message: {str(e)}")

def on_disconnect(client, userdata, rc):
    """Callback for when the MQTT client disconnects"""
    if rc != 0:
        logging.warning(f"Unexpected MQTT disconnection with code {rc}")
    else:
        logging.info("Disconnected from MQTT broker")

def handle_imu_data_message(payload):
    """Handle incoming IMU data via MQTT"""
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
        
        # Process each sensor reading in the payload
        for reading in imu_payload:
            if not isinstance(reading, dict):
                logging.error("Each reading must be a JSON object")
                continue
            
            # Validate required fields in each reading
            if 'name' not in reading or 'values' not in reading:
                logging.error("Each reading must contain name and values")
                continue

            # Validate and process the sensor reading
            try:
                process_sensor_reading(reading)
            except ValueError as ve:
                logging.error(f"Invalid sensor reading: {str(ve)}")
                continue


        logging.info(f"Processed IMU data from device: {device_id} (messages: {len(imu_payload)})")
        
    except Exception as e:
        logging.error(f"Error handling IMU data message: {str(e)}")

def process_sensor_reading(reading):
    """Process a single sensor reading and add it to the appropriate buffer"""
    name = reading['name']
    values = reading['values']
    
    # Add reading to the appropriate buffer based on the sensor name
    if name == 'accelerometer':
        validate_sensor_values(values, name)
        add_to_buffer(values, accelerometer_data_buffer)
    elif name == 'gyroscope':
        validate_sensor_values(values, name)
        add_to_buffer(values, gyroscope_data_buffer)
    elif name == 'gravity':
        validate_sensor_values(values, name)
        add_to_buffer(values, gravity_data_buffer)
    elif name == 'totalacceleration':
        validate_sensor_values(values, name)
        add_to_buffer(values, total_acceleration_data_buffer)
    elif name == 'orientation':
        validate_sensor_values(values, name)
        add_to_buffer(values, orientation_data_buffer)
    else:
        logging.warning(f"Unknown sensor type: {name}")

def validate_sensor_values(values, name):
    """Validate the structure of sensor values"""
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

def add_to_buffer(data, buffer):
    """Add data to the buffer and maintain its size"""
    buffer.append(data)
    if len(buffer) > MAX_BUFFER_SIZE:
        buffer.pop(0)  # Remove oldest data if buffer exceeds max size

def get_current_buffer_size():
    """Get the total size of all buffers"""
    return (len(accelerometer_data_buffer) + len(gyroscope_data_buffer) +
            len(gravity_data_buffer) + len(total_acceleration_data_buffer) +
            len(orientation_data_buffer))

def publish_recording_command(command):
    """Publish recording command to devices"""
    if mqtt_client and mqtt_client.is_connected():
        try:
            result = mqtt_client.publish(
                MQTT_TOPICS['recording_control'], 
                json.dumps(command),
                qos=1
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"Published recording command: {command['command']}")
            else:
                logging.error(f"Failed to publish recording command: {result.rc}")
        except Exception as e:
            logging.error(f"Error publishing recording command: {str(e)}")

def publish_status_update():
    """Publish current server status"""
    if mqtt_client and mqtt_client.is_connected():
        try:
            status = {
                'recording_state': current_recording_state.value,
                'active_sessions': list(active_recording_sessions),
                'buffer_size': get_current_buffer_size(),
                'timestamp': datetime.now().isoformat(),
                'service': 'imu-mqtt-service',
                'mqtt_status': 'connected',
                'uptime_seconds': time.time() - start_time,
            }
            result = mqtt_client.publish(
                MQTT_TOPICS['status'], 
                json.dumps(status),
                qos=0
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.debug(f"Published status update")
        except Exception as e:
            logging.error(f"Error publishing status update: {str(e)}")

def init_mqtt_client():
    """Initialize and start MQTT client"""
    global mqtt_client
    
    mqtt_client = mqtt.Client(config['mqtt']['client_id'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    try:
        mqtt_client.connect(
            config['mqtt']['broker_host'], 
            config['mqtt']['broker_port'], 
            60
        )
        # Start the MQTT loop in a separate thread
        mqtt_client.loop_start()
        logging.info("MQTT client initialized and connected")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize MQTT client: {str(e)}")
        return False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global service_running
    logging.info(f"Received signal {signum}. Shutting down...")
    service_running = False
    
    # Publish service shutdown announcement
    if mqtt_client and mqtt_client.is_connected():
        shutdown_announcement = {
            'service': 'imu-mqtt-service',
            'status': 'offline',
            'timestamp': datetime.now().isoformat(),
            'reason': 'shutdown'
        }
        mqtt_client.publish("imu/service/announce", json.dumps(shutdown_announcement), qos=1)
        time.sleep(1)  # Give time for message to be sent
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    
    sys.exit(0)

def status_update_thread():
    """Background thread to periodically publish status updates"""
    while service_running:
        try:
            publish_status_update()
            time.sleep(30)
        except Exception as e:
            logging.error(f"Error in status update thread: {str(e)}")

def main():
    """Main service function"""
    global start_time, service_running
    
    start_time = time.time()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize MQTT client
    if not init_mqtt_client():
        logging.error("Failed to initialize MQTT client. Exiting.")
        sys.exit(1)
    
    # Start background status update thread
    status_thread = threading.Thread(target=status_update_thread, daemon=True)
    status_thread.start()
    
    try:
        # Keep the service running
        while service_running:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == '__main__':
    main()
