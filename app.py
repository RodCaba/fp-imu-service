from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('imu_server.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# In-memory buffer to store IMU data
accelerometer_data_buffer = []
gyroscope_data_buffer = []
gravity_data_buffer = []
total_acceleration_data_buffer = []
orientation_data_buffer = []
MAX_BUFFER_SIZE = 1000

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'buffer_size': get_current_buffer_size()
    })

@app.route('/data', methods=['POST'])
def receive_imu_data():
    """
    Receive IMU data from mobile devices
    Expected JSON format:
    {
        "messageId": number,
        "sessionId": string (UUID),
        "deviceId": string (UUID),
        "payload": array of sensor readings
    }
    """
    try:
        # Check if request contains JSON data
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()

        # Get payload
        payload = data.get('payload', [])

        if not isinstance(payload, list) or not payload:
            return jsonify({'error': 'Payload must be a non-empty array'}), 400
        
        # Process each sensor reading in the payload
        for reading in payload:
            if not isinstance(reading, dict):
                return jsonify({'error': 'Each reading must be a JSON object'}), 400
            
            # Validate required fields in each reading
            if 'name' not in reading or 'values' not in reading:
                return jsonify({'error': 'Each reading must contain name and values'}), 400

            # Validate the structure of the sensor reading
            try:
                process_sensor_reading(reading)
            except ValueError as ve:
                return jsonify({'error': str(ve)}), 400

        logging.info(f"Received IMU data from device: {data.get('deviceId', 'unknown')}")
        
        return jsonify({
            'status': 'success',
            'message': 'IMU data received successfully',
            'buffer_size': get_current_buffer_size(),
        }), 200
        
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        logging.error(f"Error processing IMU data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


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
        return

def validate_sensor_values(values, name):
    """ Validate the structure of sensor values """
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

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=8000,
        debug=False, 
        threaded=True  # Handle multiple requests concurrently
    )
