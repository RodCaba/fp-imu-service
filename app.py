import json
import logging
import threading
import time
import signal
import sys
from src.mqtt_broker.mqtt_broker import MQTTBroker
from src.imu_buffer import IMUBuffer
from src.mqtt_broker.factories.mqtt_broker_factory import MQTTBrokerFactory

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

def status_update_thread(mqtt_broker: MQTTBroker):
    """Background thread to periodically publish status updates"""
    while mqtt_broker.service_running:
        try:
            mqtt_broker.publish_status_update()
            time.sleep(30)
        except Exception as e:
            logging.error(f"Error in status update thread: {str(e)}")

def main():
    """Main service function"""
    imu_buffer = IMUBuffer(config)
    mqtt_broker = MQTTBrokerFactory.create_production_broker(config, imu_buffer)

    if not mqtt_broker.service_running:
        logging.error("Failed to initialize MQTT broker. Exiting.")
        sys.exit(1)

    network_ip = mqtt_broker.get_ip_address()
    logging.info(f"Service running on IP: {network_ip}")
    logging.info("MQTT broker accessible at: %s:%d", network_ip, config['mqtt']['broker_port'])

    signal.signal(signal.SIGINT, mqtt_broker.signal_handler)
    signal.signal(signal.SIGTERM, mqtt_broker.signal_handler)
    

    # Start background status update thread
    status_thread = threading.Thread(target=status_update_thread, args=(mqtt_broker,), daemon=True)
    status_thread.start()
    
    try:
        # Keep the service running
        while mqtt_broker.service_running:
            time.sleep(1)
    except KeyboardInterrupt:
        mqtt_broker.signal_handler(signal.SIGINT, None)
        sys.exit(0)

if __name__ == '__main__':
    main()
