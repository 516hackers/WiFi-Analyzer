"""
WiFi Analyzer Pro - Complete Network Monitoring Solution
Compatible with Android via Kivy + Buildozer
"""

import subprocess
import re
import threading
import time
from datetime import datetime
from collections import defaultdict
import socket
import struct
import os

# Try importing required packages
try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.progressbar import ProgressBar
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp
    from kivy.utils import get_color_from_hex
    from kivy.logger import Logger
    
    import psutil
    import speedtest
except ImportError as e:
    print(f"Error importing packages: {e}")
    print("Please install required packages: pip install kivy psutil speedtest-cli")
    exit(1)

class WiFiAnalyzer:
    """Core WiFi analysis functionality"""
    
    @staticmethod
    def get_connected_devices():
        """Get list of devices connected to the network using ARP table"""
        devices = []
        try:
            # Try different methods based on platform
            if os.name == 'nt':  # Windows
                output = subprocess.check_output(['arp', '-a'], text=True, stderr=subprocess.DEVNULL)
                pattern = r'(\d+\.\d+\.\d+\.\d+)\s+([a-fA-F0-9:-]{17})'
                matches = re.findall(pattern, output)
                for ip, mac in matches:
                    if not ip.startswith('224.') and not ip.startswith('255.'):
                        devices.append({
                            'ip': ip,
                            'mac': mac,
                            'hostname': WiFiAnalyzer.get_hostname(ip)
                        })
            else:  # Linux/Android
                # Try reading /proc/net/arp first (works on Android)
                if os.path.exists('/proc/net/arp'):
                    with open('/proc/net/arp', 'r') as f:
                        for line in f.readlines()[1:]:
                            parts = line.split()
                            if len(parts) >= 4 and parts[2] == '0x2':
                                devices.append({
                                    'ip': parts[0],
                                    'mac': parts[3],
                                    'hostname': WiFiAnalyzer.get_hostname(parts[0])
                                })
                # Try arp command as fallback
                else:
                    try:
                        output = subprocess.check_output(['arp', '-n'], text=True, stderr=subprocess.DEVNULL)
                        pattern = r'(\d+\.\d+\.\d+\.\d+).*?([a-fA-F0-9:]{17})'
                        matches = re.findall(pattern, output)
                        for ip, mac in matches:
                            if not ip.startswith('224.') and not ip.startswith('255.'):
                                devices.append({
                                    'ip': ip,
                                    'mac': mac,
                                    'hostname': WiFiAnalyzer.get_hostname(ip)
                                })
                    except:
                        pass
        except Exception as e:
            Logger.warning(f"Error getting devices: {e}")
            
        # Remove duplicates
        unique_devices = {}
        for device in devices:
            if device['ip'] not in unique_devices:
                unique_devices[device['ip']] = device
        
        return list(unique_devices.values())
    
    @staticmethod
    def get_hostname(ip):
        """Get hostname from IP address"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return "Unknown"
    
    @staticmethod
    def get_wifi_info():
        """Get current WiFi connection information"""
        wifi_info = {
            'ssid': 'Not Connected',
            'signal': 0,
            'rssi': 0
        }
        
        try:
            if os.name == 'nt':  # Windows
                output = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], text=True, stderr=subprocess.DEVNULL)
                ssid_match = re.search(r'SSID\s*:\s*(.+)', output)
                signal_match = re.search(r'Signal\s*:\s*(\d+)%', output)
                
                if ssid_match:
                    wifi_info['ssid'] = ssid_match.group(1).strip()
                if signal_match:
                    wifi_info['signal'] = int(signal_match.group(1))
                    
            else:  # Linux/Android
                # Try iwgetid for SSID
                try:
                    output = subprocess.check_output(['iwgetid', '-r'], text=True, stderr=subprocess.DEVNULL)
                    if output.strip():
                        wifi_info['ssid'] = output.strip()
                except:
                    pass
                
                # Try wpa_cli for Android
                if wifi_info['ssid'] == 'Not Connected':
                    try:
                        output = subprocess.check_output(['wpa_cli', '-i', 'wlan0', 'status'], text=True, stderr=subprocess.DEVNULL)
                        ssid_match = re.search(r'ssid=(.+)', output)
                        if ssid_match:
                            wifi_info['ssid'] = ssid_match.group(1)
                    except:
                        pass
                
                # Get signal strength
                try:
                    output = subprocess.check_output(['iwconfig'], text=True, stderr=subprocess.DEVNULL)
                    signal_match = re.search(r'Signal level=(-\d+) dBm', output)
                    if signal_match:
                        wifi_info['rssi'] = int(signal_match.group(1))
                        wifi_info['signal'] = min(100, max(0, (wifi_info['rssi'] + 100) * 2))
                except:
                    pass
                    
        except Exception as e:
            Logger.warning(f"Error getting WiFi info: {e}")
            
        return wifi_info
    
    @staticmethod
    def get_router_health():
        """Get router health metrics"""
        health = {
            'latency': 0,
            'packet_loss': 0,
            'router_ip': '192.168.1.1',
            'status': 'Unknown'
        }
        
        try:
            # Get default gateway
            if os.name == 'nt':
                output = subprocess.check_output(['ipconfig'], text=True, stderr=subprocess.DEVNULL)
                gateway_match = re.search(r'Default Gateway.*?: ([\d\.]+)', output)
            else:
                try:
                    output = subprocess.check_output(['ip', 'route', 'show', 'default'], text=True, stderr=subprocess.DEVNULL)
                    gateway_match = re.search(r'default via ([\d\.]+)', output)
                except:
                    # Fallback to common router IPs
                    gateway_match = None
                    health['router_ip'] = '192.168.1.1'
            
            if gateway_match:
                health['router_ip'] = gateway_match.group(1)
                
                # Ping router with timeout
                if os.name == 'nt':
                    ping_cmd = ['ping', '-n', '4', '-w', '1000', health['router_ip']]
                else:
                    ping_cmd = ['ping', '-c', '4', '-W', '1', health['router_ip']]
                
                output = subprocess.check_output(ping_cmd, text=True, stderr=subprocess.DEVNULL)
                
                # Get latency
                latency_match = re.search(r'time[=<](\d+\.?\d*)\s*ms', output)
                if latency_match:
                    health['latency'] = float(latency_match.group(1))
                else:
                    # Try alternative pattern for ping output
                    latency_match = re.search(r'=\s*(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)', output)
                    if latency_match:
                        health['latency'] = float(latency_match.group(2))
                
                # Get packet loss
                loss_match = re.search(r'(\d+)% loss', output)
                if loss_match:
                    health['packet_loss'] = int(loss_match.group(1))
                else:
                    loss_match = re.search(r'(\d+)\s*%', output)
                    if loss_match:
                        health['packet_loss'] = int(loss_match.group(1))
                
                # Determine status
                if health['packet_loss'] == 100:
                    health['status'] = 'Offline'
                elif health['packet_loss'] > 20:
                    health['status'] = 'Poor'
                elif health['latency'] > 200:
                    health['status'] = 'Slow'
                elif health['latency'] > 100:
                    health['status'] = 'Degraded'
                else:
                    health['status'] = 'Healthy'
                    
        except Exception as e:
            health['status'] = 'Unreachable'
            Logger.warning(f"Error checking router health: {e}")
            
        return health
    
    @staticmethod
    def get_network_usage():
        """Get current network usage"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent / (1024 * 1024),
                'bytes_recv': net_io.bytes_recv / (1024 * 1024),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except Exception as e:
            Logger.warning(f"Error getting network usage: {e}")
            return {
                'bytes_sent': 0,
                'bytes_recv': 0,
                'packets_sent': 0,
                'packets_recv': 0
            }
    
    @staticmethod
    def measure_speed():
        """Measure internet speed"""
        try:
            # Use speedtest with timeout
            st = speedtest.Speedtest()
            st.get_best_server()
            download = st.download() / (1024 * 1024)
            upload = st.upload() / (1024 * 1024)
            ping = st.results.ping
            
            return {
                'download': round(download, 2),
                'upload': round(upload, 2),
                'ping': round(ping, 2)
            }
        except Exception as e:
            Logger.warning(f"Speed test error: {e}")
            return {
                'download': 0,
                'upload': 0,
                'ping': 0,
                'error': str(e)
            }

# Rest of the UI code remains the same as in the previous response...
# (Keep the WiFiAnalyzerUI and WiFiAnalyzerApp classes from the previous response)

if __name__ == '__main__':
    WiFiAnalyzerApp().run()
