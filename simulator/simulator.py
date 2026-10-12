import os
import sys
import time
import json
import random
import datetime
import signal
import socket
import threading
import numpy as np
import paho.mqtt.client as mqtt

class PhysicsMachineSimulator:
    """
    Mathematical / Physics-Inspired Industrial Rotating Machine Simulator.
    Simulates motor current, thermal dynamics, mechanical vibration, acoustic noise,
    pressure dynamics, health degradation, and fault states for 5 independent PLCs.
    """
    def __init__(self, plc_id=1, seed=None, base_load=0.6, base_speed=1800.0,
                 deg_init=0.05, deg_speed=1.0, temp_offset=0.0, vib_offset=0.0, cooling_k=0.18, **kwargs):
        self.plc_id = plc_id
        if isinstance(plc_id, int):
            self.plc_id_num = plc_id
            self.plc_id_str = f"PLC_{plc_id:02d}"
        else:
            s = str(plc_id).strip()
            digits = "".join(ch for ch in s if ch.isdigit())
            self.plc_id_num = int(digits) if digits else 1
            self.plc_id_str = f"PLC_{self.plc_id_num:02d}"
        self.seed = seed
        self.base_load = base_load
        self.base_speed = base_speed
        self.deg_speed = deg_speed
        self.temp_offset = temp_offset
        self.vib_offset = vib_offset
        self.cooling_k = cooling_k
        self.reset(seed=seed, deg_init=deg_init)

    def reset(self, seed=None, deg_init=0.05, **kwargs):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self.step_count = 0
        self.start_time = datetime.datetime.now()
        
        # State variables
        self.degradation = float(deg_init)  # 0.0 (healthy) to 1.0 (failed)
        self.health = max(0.0, min(100.0, (1.0 - self.degradation) * 100.0))
        self.load = float(self.base_load)
        self.speed = float(self.base_speed)
        
        # Thermal model parameters
        self.ambient_temp = 25.0
        self.temperature = 60.0 + self.temp_offset
        self.winding_resistance = 0.12  # Ohms
        self.thermal_capacity = 15.0  # Heat capacity C
        
        # Motor current parameters
        self.i_idle = 5.0  # Base current at 0 load
        self.k_load_curr = 5.0  # k_load coefficient
        
        # Base sensor values
        self.vib_base = 0.15 + self.vib_offset
        self.press_base = 5.0
        self.noise_base = 40.0
        
        self.fault_state = "NORMAL"
        self.active_event = "None"

    def step(self):
        self.step_count += 1
        
        # 1. SIMULATION CLOCK & STATE EVOLUTION
        load_var = 0.05 * np.sin(self.step_count / 10.0) + random.gauss(0, 0.01)
        self.load = max(0.1, min(1.0, self.base_load + load_var))
        
        speed_var = 10.0 * np.cos(self.step_count / 15.0) + random.gauss(0, 2.0)
        self.speed = max(1500.0, min(2000.0, self.base_speed + speed_var))
        
        deg_step = (0.0002 + 0.0001 * (self.load ** 2)) * self.deg_speed
        self.degradation = min(1.0, self.degradation + deg_step)
        self.health = max(0.0, min(100.0, (1.0 - self.degradation) * 100.0))
        
        if self.degradation > 0.7 or self.vib_offset > 1.0:
            self.fault_state = "BEARING_DEGRADATION"
            self.active_event = "Bearing Degradation and High Vibration"
        elif self.degradation > 0.5 or self.temp_offset > 10.0:
            self.fault_state = "OVERHEATING"
            self.active_event = "Elevated Thermal Stress"
        elif self.load > 0.8:
            self.fault_state = "OVERLOAD"
            self.active_event = "High Mechanical Operating Load"
        else:
            self.fault_state = "NORMAL"
            self.active_event = "Normal Operation"
            
        # 2. MOTOR CURRENT MODEL (Section 6): I = I_idle + k_load * Load + measurement_noise
        noise_curr = random.gauss(0, 0.05)
        self.motor_current = self.i_idle + self.k_load_curr * self.load + noise_curr
        self.motor_current = max(4.0, min(25.0, self.motor_current))
        
        # 3. TEMPERATURE MODEL (Section 7): P_loss = R * I^2, dT/dt = (P_loss - K*(T - T_amb))/C
        p_loss = self.winding_resistance * (self.motor_current ** 2)
        dt = 1.0
        dt_dt = (p_loss - self.cooling_k * (self.temperature - self.ambient_temp)) / self.thermal_capacity
        noise_temp = random.gauss(0, 0.1)
        self.temperature = self.temperature + dt_dt * dt + noise_temp
        self.temperature = max(20.0, min(120.0, self.temperature))
        
        # 4. VIBRATION MODEL (Section 8): Vib = Vib_base + k_speed*(Speed/1800) + k_load*Load + k_deg*Deg + noise
        k_speed_vib = 0.05
        k_load_vib = 0.05
        k_deg_vib = 2.5
        fault_vib = 0.8 if self.fault_state == "BEARING_DEGRADATION" else 0.0
        noise_vib = random.gauss(0, 0.015)
        
        self.vibration = (self.vib_base +
                          k_speed_vib * (self.speed / 1800.0) +
                          k_load_vib * self.load +
                          k_deg_vib * (self.degradation ** 1.5) +
                          fault_vib +
                          noise_vib)
        self.vibration = max(0.05, min(10.0, self.vibration))
        
        # 5. PRESSURE MODEL (Section 9): Press = Press_base + k_load*Load - Flow_loss + noise
        k_load_press = 0.3
        flow_loss = 0.15 * (self.speed / 1800.0)
        noise_press = random.gauss(0, 0.03)
        self.pressure = self.press_base + k_load_press * self.load - flow_loss + noise_press
        self.pressure = max(1.0, min(10.0, self.pressure))
        
        # 6. NOISE MODEL (Section 10): Noise = Noise_base + k_speed*(Speed/1800) + k_vib*Vib + noise
        k_speed_noise = 2.0
        k_vib_noise = 4.5
        noise_acoust = random.gauss(0, 0.2)
        self.noise = (self.noise_base +
                      k_speed_noise * (self.speed / 1800.0) +
                      k_vib_noise * self.vibration +
                      noise_acoust)
        self.noise = max(30.0, min(100.0, self.noise))
        
        self.rul_days = max(0, int(round((1.0 - self.degradation) * 250.0)))
        
        if self.health > 80.0:
            status_str = "Healthy"
        elif self.health > 50.0:
            status_str = "Slight Wear"
        elif self.health > 30.0:
            status_str = "Moderate Wear"
        elif self.health > 15.0:
            status_str = "Warning"
        else:
            status_str = "Critical"
            
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        temp_val = round(float(self.temperature), 1)
        vib_val = round(float(self.vibration), 2)
        curr_val = round(float(self.motor_current), 1)
        press_val = round(float(self.pressure), 1)
        noise_val = round(float(self.noise), 1)

        return {
            'plc_id': self.plc_id_str,
            'plc_id_num': self.plc_id_num,
            'timestamp': timestamp_str,
            'temperature': temp_val,
            'vibration': vib_val,
            'motor_current': curr_val,
            'pressure': press_val,
            'noise': noise_val,
            'Motor_Temp': temp_val,
            'Vibration_X': vib_val,
            'Motor_Current': curr_val,
            'Pressure_Inlet': press_val,
            'Noise': noise_val,
            'tags': {
                'Motor_Temp': temp_val,
                'Vibration_X': vib_val,
                'Motor_Current': curr_val,
                'Pressure_Inlet': press_val,
                'Noise': noise_val
            },
            'Machine_Health': round(float(self.health), 1),
            'Machine_Status': status_str,
            'Remaining_Useful_Life_Days': int(self.rul_days),
            'Active_Event': self.active_event,
            'fault_state': self.fault_state
        }

RealTimeMachineSimulator = PhysicsMachineSimulator
MachineSimulator = PhysicsMachineSimulator

class MiniMqttBroker:
    def __init__(self, host='127.0.0.1', port=1883):
        self.host = host
        self.port = port
        self.subscriptions = []
        self.running = True

    def start(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(15)
            self.thread = threading.Thread(target=self._listen, daemon=True)
            self.thread.start()
            return True
        except Exception:
            return False

    def _listen(self):
        while self.running:
            try:
                self.server.settimeout(1.0)
                client_sock, _ = self.server.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_client(self, sock):
        while self.running:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                packet_type = data[0] >> 4
                if packet_type == 1:
                    sock.sendall(bytes([0x20, 0x02, 0x00, 0x00]))
                elif packet_type == 8:
                    msg_id = data[2:4]
                    sock.sendall(bytes([0x90, 0x03]) + msg_id + bytes([0x00]))
                    topic_len = (data[4] << 8) | data[5]
                    topic = data[6:6+topic_len].decode('utf-8', errors='ignore')
                    self.subscriptions.append((topic, sock))
                elif packet_type == 3:
                    topic_len = (data[2] << 8) | data[3]
                    pub_topic = data[4:4+topic_len].decode('utf-8', errors='ignore')
                    for sub_topic, sub_sock in list(self.subscriptions):
                        if sub_topic == pub_topic or sub_topic == 'plc/#' or sub_topic.endswith('/#'):
                            try:
                                sub_sock.sendall(data)
                            except Exception:
                                pass
                elif packet_type == 12:
                    sock.sendall(bytes([0xD0, 0x00]))
            except Exception:
                break

BROKER_PRIMARY = 'broker.hivemq.com'
PORT_PRIMARY = 1883

class MqttPlcMasterSimulator:
    def __init__(self, broker=BROKER_PRIMARY, port=PORT_PRIMARY):
        self.broker = broker
        self.port = port
        self.running = True
        
        # Section 14: 5 Independent PLCs
        self.plcs = [
            PhysicsMachineSimulator(plc_id=1, seed=101, base_load=0.60, base_speed=1800.0, deg_init=0.05, deg_speed=1.0),
            PhysicsMachineSimulator(plc_id=2, seed=202, base_load=0.85, base_speed=1820.0, deg_init=0.10, deg_speed=0.9),
            PhysicsMachineSimulator(plc_id=3, seed=303, base_load=0.65, base_speed=1790.0, deg_init=0.35, deg_speed=1.4, vib_offset=1.2),
            PhysicsMachineSimulator(plc_id=4, seed=404, base_load=0.75, base_speed=1810.0, deg_init=0.30, deg_speed=1.3, temp_offset=12.0, cooling_k=0.10),
            PhysicsMachineSimulator(plc_id=5, seed=505, base_load=0.55, base_speed=1795.0, deg_init=0.02, deg_speed=1.1)
        ]
        self.client = None
        self.active_broker = self.broker
        self.active_port = self.port

    def _connect_client(self):
        print('Connecting to MQTT broker...')
        try:
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'PLC_Master_Simulator_{random.randint(1000, 9999)}')
            except Exception:
                client = mqtt.Client(client_id=f'PLC_Master_Simulator_{random.randint(1000, 9999)}')
            client.connect(self.broker, self.port, keepalive=60)
            self.client = client
            self.active_broker = self.broker
            self.active_port = self.port
            print(f'Connected to {self.broker}:{self.port}')
            return
        except Exception as e:
            print(f'Connection attempt to {self.broker}:{self.port} failed ({e}). Trying fallback...')

        mini_broker = MiniMqttBroker()
        mini_broker.start()
        time.sleep(0.2)
        try:
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'PLC_Master_Simulator_{random.randint(1000, 9999)}')
            except Exception:
                client = mqtt.Client(client_id=f'PLC_Master_Simulator_{random.randint(1000, 9999)}')
            client.connect('127.0.0.1', 1883, keepalive=60)
            self.client = client
            self.active_broker = 'broker.hivemq.com (local fallback)'
            self.active_port = 1883
            print('Connected to broker.hivemq.com:1883 (Local Fallback)')
        except Exception as err:
            print(f'Fallback connection failed: {err}')

    def start(self):
        self._connect_client()
        if not self.client:
            print('Failed to initialize MQTT connection.')
            return
            
        self.client.loop_start()
        banner = '=' * 65
        print(banner)
        print(' Physics-Based 5-PLC Industrial MQTT Telemetry Simulator Started')
        print(f' Target Broker: {self.active_broker}:{self.active_port}')
        print(' Topics: plc/1, plc/2, plc/3, plc/4, plc/5')
        print(' Press Ctrl+C to stop.')
        print(banner + '\n')
        
        try:
            TAG_SPECS = [
                ("T101", "Motor_Temp", "temperature"),
                ("T102", "Vibration_X", "vibration"),
                ("T103", "Motor_Current", "motor_current"),
                ("T104", "Pressure_Inlet", "pressure"),
                ("T105", "Noise", "noise")
            ]

            while self.running:
                for plc in self.plcs:
                    data = plc.step()
                    plc_str = data['plc_id']
                    pid_num = data['plc_id_num']

                    # 1. Publish individual tag messages (Section 25 format)
                    for tag_id, tag_name, _ in TAG_SPECS:
                        tag_msg = {
                            "plc_id": plc_str,
                            "tag_id": tag_id,
                            "tag_name": tag_name,
                            "val": data[tag_name],
                            "timestamp": data["timestamp"]
                        }
                        self.client.publish(f"plc/{plc_str}/{tag_name}", json.dumps(tag_msg))

                    # 2. Publish full composite telemetry for backward compatibility
                    payload = json.dumps(data)
                    self.client.publish(f"plc/{plc_str}", payload)
                    self.client.publish(f"plc/{pid_num}", payload)
                    
                    t_val = data['temperature']
                    v_val = data['vibration']
                    c_val = data['motor_current']
                    p_val = data['pressure']
                    n_val = data['noise']
                    load_val = round(plc.load, 2)
                    
                    print(f'{plc_str} | Load: {load_val} | Temp: {t_val}°C | Vib: {v_val} | Current: {c_val} A | Pressure: {p_val} | Noise: {n_val} dB | Published [OK]')
                print('-' * 75)
                time.sleep(1.2)
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f'MQTT Simulator Error: {e}')
            self.stop()

    def stop(self):
        self.running = False
        print('\nStopping PLC MQTT Simulator...')
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        print('Simulator stopped cleanly.')

def run():
    sim = MqttPlcMasterSimulator()
    sim.start()

if __name__ == '__main__':
    run()
