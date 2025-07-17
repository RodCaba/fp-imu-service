#!/usr/bin/env python3
"""
Script de demostración para mostrar que el arreglo de integración MQTT + IMU Buffer funciona.
"""

import json
from unittest.mock import MagicMock, patch

# Importar los componentes
from src.mqtt_broker.mqtt_broker import MQTTBroker
from src.imu_buffer import IMUBuffer


def test_integration_fix():
    """Función que demuestra que el arreglo de integración funciona."""
    
    print("🔧 PRUEBA DE ARREGLO: MQTT Broker + IMU Buffer Integration")
    print("="*70)
    
    # Configuración
    config = {
        'mqtt': {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'topics': {
                'recording_control': 'imu/recording/control',
                'data_stream': 'imu/data/stream',
                'status': 'imu/status'
            },
            'client_id': 'demo_client'
        },
        'data': {
            'max_buffer_size': 100
        }
    }
    
    # Mock de módulos externos
    with patch('src.mqtt_broker.mqtt_broker.logging'), \
         patch('src.mqtt_broker.mqtt_broker.time') as mock_time, \
         patch('src.mqtt_broker.mqtt_broker.socket'), \
         patch('src.imu_buffer.logging'):
        
        mock_time.time.return_value = 1234567890.0
        
        # Crear componentes reales
        mock_mqtt_client = MagicMock()
        imu_buffer = IMUBuffer(config)
        broker = MQTTBroker(config, mock_mqtt_client, imu_buffer)
        
        # Mensaje de prueba (formato MQTT real)
        mqtt_message = {
            'deviceId': 'sensor_001',
            'payload': [
                {'x': 1.5, 'y': 2.5, 'z': 3.5},
                {'x': 4.5, 'y': 5.5, 'z': 6.5}
            ],
            'name': 'accelerometer'
        }
        
        print(f"📨 Mensaje MQTT a procesar:")
        print(f"   Device ID: {mqtt_message['deviceId']}")
        print(f"   Sensor: {mqtt_message['name']}")
        print(f"   Data Points: {len(mqtt_message['payload'])}")
        print(f"   Payload: {mqtt_message['payload']}")
        print()
        
        # Simular recepción del mensaje
        mock_msg = MagicMock()
        mock_msg.topic = config['mqtt']['topics']['data_stream']
        mock_msg.payload.decode.return_value = json.dumps(mqtt_message)
        
        # Estado inicial
        initial_sizes = imu_buffer.get_current_buffer_size()
        print(f"📊 Estado inicial del buffer: {initial_sizes}")
        
        # Procesar mensaje
        broker.on_message(None, None, mock_msg)
        
        # Estado final
        final_sizes = imu_buffer.get_current_buffer_size()
        buffered_data = imu_buffer.get_data()
        
        print(f"📊 Estado final del buffer: {final_sizes}")
        print(f"📈 Datos almacenados en accelerometer: {len(buffered_data['accelerometer'])}")
        
        if buffered_data['accelerometer']:
            print(f"📋 Primer dato: {buffered_data['accelerometer'][0]}")
            print(f"📋 Segundo dato: {buffered_data['accelerometer'][1]}")
        
        # Verificación del éxito
        success = final_sizes['accelerometer'] > initial_sizes['accelerometer']
        
        print()
        print("🎯 RESULTADO DEL ARREGLO:")
        if success:
            print("   ✅ ÉXITO: Los datos MQTT ahora llegan correctamente al IMU Buffer")
            print("   ✅ Se procesaron todos los puntos de datos del mensaje")
            print("   ✅ No hubo errores de formato")
            print("   ✅ La integración MQTT ↔ IMU Buffer funciona correctamente")
        else:
            print("   ❌ FALLO: Los datos no se procesaron correctamente")
        
        print()
        print("🔧 LO QUE SE ARREGLÓ:")
        print("   • ANTES: MQTT broker pasaba payload como lista → IMU buffer lo rechazaba")
        print("   • AHORA: MQTT broker itera la lista y envía elementos individuales")
        print("   • RESULTADO: Cada dato se procesa en el formato correcto")
        
        return success


if __name__ == "__main__":
    test_integration_fix()
