import socket
import paho.mqtt.client as mqtt
import time

def test_port_open(host, port):
    """Test if MQTT port is accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def test_mqtt_connection(host, port):
    """Test actual MQTT connection"""
    connected = False
    
    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        connected = (rc == 0)
        
    client = mqtt.Client("network_test")
    client.on_connect = on_connect
    
    try:
        client.connect(host, port, 10)
        client.loop_start()
        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        return connected
    except:
        return False

# Test both localhost and network IP
hosts_to_test = [
    ("localhost", 1883),
    ("192.168.1.209", 1883),
    ("172.24.68.228", 1883),
]

print("Testing MQTT connectivity...")
print()

for host, port in hosts_to_test:
    print(f"Testing {host}:{port}")
    
    # Test port
    port_open = test_port_open(host, port)
    print("Port reachable: ", "true" if port_open else "false")
    
    if port_open:
        # Test MQTT
        mqtt_works = test_mqtt_connection(host, port)
        print("MQTT works: ", "true" if mqtt_works else "false")

    print()