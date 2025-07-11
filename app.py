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
imu_data_buffer = []
MAX_BUFFER_SIZE = 1000

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'buffer_size': len(imu_data_buffer)
    })

@app.route('/data', methods=['POST'])
def receive_imu_data():
    """
    Receive IMU data from mobile devices
    Expected JSON format:
    {
        "timestamp": "ISO timestamp",
        "accelerometer": {"x": float, "y": float, "z": float},
        "gyroscope": {"x": float, "y": float, "z": float},
        "magnetometer": {"x": float, "y": float, "z": float},
        "device_id": "string"
    }
    """
    try:
        # Check if request contains JSON data
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        print(f"Received data: {data}")
        
        # Validate required fields
        required_fields = ['timestamp', 'accelerometer', 'gyroscope']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate accelerometer data
        accel = data.get('accelerometer', {})
        if not all(key in accel for key in ['x', 'y', 'z']):
            return jsonify({'error': 'Accelerometer data must contain x, y, z values'}), 400
        
        # Validate gyroscope data
        gyro = data.get('gyroscope', {})
        if not all(key in gyro for key in ['x', 'y', 'z']):
            return jsonify({'error': 'Gyroscope data must contain x, y, z values'}), 400
        
        # Add server timestamp
        data['server_timestamp'] = datetime.now().isoformat()
        
        # Add to buffer
        imu_data_buffer.append(data)
        
        # Maintain buffer size
        if len(imu_data_buffer) > MAX_BUFFER_SIZE:
            imu_data_buffer.pop(0)
        
        logging.info(f"Received IMU data from device: {data.get('device_id', 'unknown')}")
        
        return jsonify({
            'status': 'success',
            'message': 'IMU data received successfully',
            'buffer_size': len(imu_data_buffer)
        }), 200
        
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        logging.error(f"Error processing IMU data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


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
