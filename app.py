import json
import logging
import threading
import time
import signal
import sys
from src.imu_buffer import IMUBuffer
from src.imu_message_handler import IMUMessageHandler
from fp_mqtt_broker import BrokerFactory
from fp_mqtt_broker import MQTTBroker
from fp_orchestrator_utils import OrchestratorClient

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
    orchestrator_client = OrchestratorClient(
        server_address=config['orchestrator']['server_address'],
        timeout=config['orchestrator'].get('timeout', 30)
    )
    imu_buffer = IMUBuffer(config, orchestrator_client)
    message_handlers = [IMUMessageHandler(imu_buffer, config, orchestrator_client)]
    broker = BrokerFactory.create_broker(config, message_handlers)
    is_connected = broker.connect()

    if not is_connected:
        logging.error("Failed to connect to MQTT broker. Exiting service.")
        sys.exit(1)
    logging.info("MQTT broker service started successfully")
    
    network_ip = broker.get_ip_address()
    logging.info(f"Service running on IP: {network_ip}")
    logging.info("MQTT broker accessible at: %s:%d", network_ip, config['mqtt']['broker_port'])

    signal.signal(signal.SIGINT, broker.signal_handler)
    signal.signal(signal.SIGTERM, broker.signal_handler)

    # Start background status update thread
    status_thread = threading.Thread(target=status_update_thread, args=(broker,), daemon=True)
    status_thread.start()
    
    try:
        # Keep the service running
        while broker.service_running:
            time.sleep(1)
    except KeyboardInterrupt:
        broker.signal_handler(signal.SIGINT, None)
        sys.exit(0)

if __name__ == '__main__':
    main()
