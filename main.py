"""
WiFi Analyzer Pro - Complete Network Monitoring Solution
Compatible with Android via Kivy + Buildozer
GitHub Actions workflow included for APK generation
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
    
    # For network monitoring
    import psutil
    import speedtest
except ImportError:
    print("Installing required packages...")
    os.system('pip install kivy psutil speedtest-cli')
    exit(1)

# Android permissions and configurations
permissions = [
    'android.permission.INTERNET',
    'android.permission.ACCESS_WIFI_STATE',
    'android.permission.CHANGE_WIFI_STATE',
    'android.permission.ACCESS_NETWORK_STATE',
    'android.permission.ACCESS_FINE_LOCATION',
    'android.permission.ACCESS_COARSE_LOCATION'
]

class WiFiAnalyzer:
    """Core WiFi analysis functionality"""
    
    @staticmethod
    def get_connected_devices():
        """Get list of devices connected to the network using ARP table"""
        devices = []
        try:
            # Get ARP table
            if os.name == 'nt':  # Windows
                output = subprocess.check_output(['arp', '-a'], text=True)
            else:  # Linux/Android/Mac
                output = subprocess.check_output(['arp', '-n'], text=True)
            
            # Parse ARP entries
            pattern = r'(\d+\.\d+\.\d+\.\d+).*?([a-fA-F0-9:]{17})'
            matches = re.findall(pattern, output)
            
            for ip, mac in matches:
                if not ip.startswith('224.') and not ip.startswith('255.'):
                    devices.append({
                        'ip': ip,
                        'mac': mac,
                        'hostname': WiFiAnalyzer.get_hostname(ip)
                    })
            
            # Also get connected WiFi clients (requires root on Android)
            try:
                if os.path.exists('/proc/net/arp'):
                    with open('/proc/net/arp', 'r') as f:
                        for line in f.readlines()[1:]:
                            parts = line.split()
                            if len(parts) >= 4 and parts[2] == '0x2':  # Reachable
                                devices.append({
                                    'ip': parts[0],
                                    'mac': parts[3],
                                    'hostname': WiFiAnalyzer.get_hostname(parts[0])
                                })
            except:
                pass
                
        except Exception as e:
            print(f"Error getting devices: {e}")
            
        return devices
    
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
            'frequency': 0,
            'channel': 0,
            'rssi': 0
        }
        
        try:
            if os.name == 'nt':  # Windows
                output = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], text=True)
                ssid_match = re.search(r'SSID\s*:\s*(.+)', output)
                signal_match = re.search(r'Signal\s*:\s*(\d+)%', output)
                
                if ssid_match:
                    wifi_info['ssid'] = ssid_match.group(1).strip()
                if signal_match:
                    wifi_info['signal'] = int(signal_match.group(1))
                    
            else:  # Linux/Android
                # Get SSID
                try:
                    output = subprocess.check_output(['iwgetid', '-r'], text=True)
                    wifi_info['ssid'] = output.strip()
                except:
                    pass
                
                # Get signal strength
                try:
                    output = subprocess.check_output(['iwconfig'], text=True)
                    signal_match = re.search(r'Signal level=(-\d+) dBm', output)
                    if signal_match:
                        wifi_info['rssi'] = int(signal_match.group(1))
                        # Convert RSSI to percentage
                        wifi_info['signal'] = min(100, max(0, (wifi_info['rssi'] + 100) * 2))
                except:
                    pass
                    
        except Exception as e:
            print(f"Error getting WiFi info: {e}")
            
        return wifi_info
    
    @staticmethod
    def get_router_health():
        """Get router health metrics (ping latency, packet loss)"""
        health = {
            'latency': 0,
            'packet_loss': 0,
            'router_ip': '192.168.1.1',
            'status': 'Unknown'
        }
        
        try:
            # Get default gateway
            if os.name == 'nt':
                output = subprocess.check_output(['ipconfig'], text=True)
                gateway_match = re.search(r'Default Gateway.*?: ([\d\.]+)', output)
            else:
                output = subprocess.check_output(['ip', 'route', 'show', 'default'], text=True)
                gateway_match = re.search(r'default via ([\d\.]+)', output)
            
            if gateway_match:
                health['router_ip'] = gateway_match.group(1)
                
                # Ping router
                if os.name == 'nt':
                    ping_cmd = ['ping', '-n', '4', health['router_ip']]
                else:
                    ping_cmd = ['ping', '-c', '4', health['router_ip']]
                
                output = subprocess.check_output(ping_cmd, text=True)
                
                # Get latency
                latency_match = re.search(r'time[=<](\d+\.?\d*)\s*ms', output)
                if latency_match:
                    health['latency'] = float(latency_match.group(1))
                
                # Get packet loss
                loss_match = re.search(r'(\d+)% loss', output)
                if loss_match:
                    health['packet_loss'] = int(loss_match.group(1))
                
                health['status'] = 'Healthy' if health['packet_loss'] < 10 and health['latency'] < 100 else 'Degraded'
            else:
                health['status'] = 'Gateway Not Found'
                
        except Exception as e:
            health['status'] = f'Error: {str(e)[:30]}'
            
        return health
    
    @staticmethod
    def get_network_usage():
        """Get current network usage in MB/s"""
        net_io = psutil.net_io_counters()
        return {
            'bytes_sent': net_io.bytes_sent / (1024 * 1024),
            'bytes_recv': net_io.bytes_recv / (1024 * 1024),
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        }
    
    @staticmethod
    def measure_speed():
        """Measure internet speed (requires external library)"""
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            download = st.download() / (1024 * 1024)  # Convert to Mbps
            upload = st.upload() / (1024 * 1024)
            ping = st.results.ping
            
            return {
                'download': round(download, 2),
                'upload': round(upload, 2),
                'ping': round(ping, 2)
            }
        except Exception as e:
            return {
                'download': 0,
                'upload': 0,
                'ping': 0,
                'error': str(e)
            }

class WiFiAnalyzerUI(BoxLayout):
    """Main UI for WiFi Analyzer App"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(10)
        
        # Set background color
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(10)])
        self.bind(size=self._update_rect, pos=self._update_rect)
        
        # Title
        title = Label(
            text="[b]WiFi Analyzer Pro[/b]",
            markup=True,
            font_size=dp(24),
            size_hint_y=0.08,
            color=get_color_from_hex('#2196F3')
        )
        self.add_widget(title)
        
        # Create scrollable content
        scroll = ScrollView(size_hint_y=0.92)
        self.content = GridLayout(cols=1, spacing=dp(15), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter('height'))
        
        # WiFi Info Section
        self.wifi_card = self.create_card("📡 WiFi Connection")
        self.wifi_ssid = self.add_info_row(self.wifi_card, "SSID:", "Scanning...")
        self.wifi_signal = self.add_info_row(self.wifi_card, "Signal:", "0%")
        self.wifi_signal_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(20))
        self.wifi_card.add_widget(self.wifi_signal_bar)
        
        # Router Health Section
        self.router_card = self.create_card("🏥 Router Health")
        self.router_status = self.add_info_row(self.router_card, "Status:", "Checking...")
        self.router_latency = self.add_info_row(self.router_card, "Latency:", "0 ms")
        self.router_loss = self.add_info_row(self.router_card, "Packet Loss:", "0%")
        self.router_ip = self.add_info_row(self.router_card, "Router IP:", "0.0.0.0")
        
        # Connected Devices Section
        self.devices_card = self.create_card("📱 Connected Devices")
        self.devices_count = self.add_info_row(self.devices_card, "Total Devices:", "0")
        self.devices_list = Label(
            text="No devices found",
            size_hint_y=None,
            text_size=(Window.width - dp(40), None),
            valign='top'
        )
        self.devices_list.bind(size=self.devices_list.setter('text_size'))
        self.devices_card.add_widget(self.devices_list)
        
        # Network Usage Section
        self.usage_card = self.create_card("📊 Network Usage")
        self.download_usage = self.add_info_row(self.usage_card, "Download Total:", "0 MB")
        self.upload_usage = self.add_info_row(self.usage_card, "Upload Total:", "0 MB")
        
        # Speed Test Section
        self.speed_card = self.create_card("⚡ Speed Test")
        self.speed_download = self.add_info_row(self.speed_card, "Download Speed:", "0 Mbps")
        self.speed_upload = self.add_info_row(self.speed_card, "Upload Speed:", "0 Mbps")
        self.speed_ping = self.add_info_row(self.speed_card, "Ping:", "0 ms")
        
        # Buttons
        button_layout = BoxLayout(size_hint_y=0.15, spacing=dp(10))
        refresh_btn = Button(text="🔄 Refresh", font_size=dp(16))
        refresh_btn.bind(on_press=self.refresh_data)
        speed_btn = Button(text="⚡ Test Speed", font_size=dp(16))
        speed_btn.bind(on_press=self.test_speed)
        button_layout.add_widget(refresh_btn)
        button_layout.add_widget(speed_btn)
        
        self.content.add_widget(self.wifi_card)
        self.content.add_widget(self.router_card)
        self.content.add_widget(self.devices_card)
        self.content.add_widget(self.usage_card)
        self.content.add_widget(self.speed_card)
        self.content.add_widget(button_layout)
        
        scroll.add_widget(self.content)
        self.add_widget(scroll)
        
        # Start auto-refresh
        self.refresh_data()
        Clock.schedule_interval(lambda dt: self.refresh_data(), 10)  # Refresh every 10 seconds
        Clock.schedule_interval(self.update_network_usage, 2)  # Update usage every 2 seconds
    
    def _update_rect(self, instance, value):
        """Update background rectangle"""
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def create_card(self, title):
        """Create a styled card container"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(10),
            spacing=dp(5),
            size_hint_y=None,
            height=dp(200)
        )
        
        with card.canvas.before:
            Color(1, 1, 1, 1)
            self.card_rect = RoundedRectangle(size=card.size, pos=card.pos, radius=[dp(10)])
        card.bind(size=self._update_card_rect, pos=self._update_card_rect)
        
        title_label = Label(
            text=f"[b]{title}[/b]",
            markup=True,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(30),
            color=get_color_from_hex('#333333')
        )
        card.add_widget(title_label)
        
        return card
    
    def _update_card_rect(self, instance, value):
        """Update card background"""
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(size=instance.size, pos=instance.pos, radius=[dp(10)])
    
    def add_info_row(self, card, label, value):
        """Add a label-value row to a card"""
        row = BoxLayout(size_hint_y=None, height=dp(30))
        label_widget = Label(
            text=label,
            font_size=dp(14),
            size_hint_x=0.4,
            halign='left',
            color=get_color_from_hex('#666666')
        )
        label_widget.bind(size=label_widget.setter('text_size'))
        value_widget = Label(
            text=value,
            font_size=dp(14),
            size_hint_x=0.6,
            halign='left',
            color=get_color_from_hex('#333333')
        )
        value_widget.bind(size=value_widget.setter('text_size'))
        row.add_widget(label_widget)
        row.add_widget(value_widget)
        card.add_widget(row)
        return value_widget
    
    def refresh_data(self, *args):
        """Refresh all data except speed test"""
        threading.Thread(target=self._refresh_data_thread, daemon=True).start()
    
    def _refresh_data_thread(self):
        """Thread function to refresh data"""
        # Get WiFi info
        wifi_info = WiFiAnalyzer.get_wifi_info()
        Clock.schedule_once(lambda dt: self.update_wifi_info(wifi_info))
        
        # Get router health
        router_health = WiFiAnalyzer.get_router_health()
        Clock.schedule_once(lambda dt: self.update_router_health(router_health))
        
        # Get connected devices
        devices = WiFiAnalyzer.get_connected_devices()
        Clock.schedule_once(lambda dt: self.update_devices(devices))
    
    def update_wifi_info(self, wifi_info):
        """Update WiFi information on UI"""
        self.wifi_ssid.text = wifi_info['ssid']
        signal_text = f"{wifi_info['signal']}%"
        if wifi_info['rssi']:
            signal_text += f" (RSSI: {wifi_info['rssi']} dBm)"
        self.wifi_signal.text = signal_text
        self.wifi_signal_bar.value = wifi_info['signal']
    
    def update_router_health(self, health):
        """Update router health information"""
        status_color = {
            'Healthy': '#4CAF50',
            'Degraded': '#FF9800',
            'Unknown': '#9E9E9E'
        }.get(health['status'], '#F44336')
        
        self.router_status.text = f"[color={status_color}]{health['status']}[/color]"
        self.router_status.markup = True
        self.router_latency.text = f"{health['latency']:.1f} ms" if health['latency'] else "N/A"
        self.router_loss.text = f"{health['packet_loss']}%"
        self.router_ip.text = health['router_ip']
    
    def update_devices(self, devices):
        """Update connected devices list"""
        unique_devices = {}
        for device in devices:
            if device['ip'] not in unique_devices:
                unique_devices[device['ip']] = device
        
        device_list = list(unique_devices.values())
        self.devices_count.text = str(len(device_list))
        
        if device_list:
            device_text = "\n".join([
                f"• {d['hostname']}\n  IP: {d['ip']}\n  MAC: {d['mac'][-8:]}\n"
                for d in device_list[:20]  # Limit to 20 devices
            ])
            self.devices_list.text = device_text
            self.devices_card.height = dp(100 + len(device_list[:20]) * dp(60))
        else:
            self.devices_list.text = "No devices found\nMake sure you're connected to WiFi"
            self.devices_card.height = dp(150)
    
    def update_network_usage(self, dt):
        """Update network usage in real-time"""
        usage = WiFiAnalyzer.get_network_usage()
        self.download_usage.text = f"{usage['bytes_recv']:.1f} MB"
        self.upload_usage.text = f"{usage['bytes_sent']:.1f} MB"
    
    def test_speed(self, *args):
        """Run speed test in separate thread"""
        self.speed_download.text = "Testing..."
        self.speed_upload.text = "Testing..."
        self.speed_ping.text = "Testing..."
        
        threading.Thread(target=self._test_speed_thread, daemon=True).start()
    
    def _test_speed_thread(self):
        """Thread function for speed test"""
        speed_data = WiFiAnalyzer.measure_speed()
        Clock.schedule_once(lambda dt: self.update_speed(speed_data))
    
    def update_speed(self, speed_data):
        """Update speed test results"""
        if 'error' in speed_data:
            self.speed_download.text = "Error"
            self.speed_upload.text = "Error"
            self.speed_ping.text = "Error"
        else:
            self.speed_download.text = f"{speed_data['download']} Mbps"
            self.speed_upload.text = f"{speed_data['upload']} Mbps"
            self.speed_ping.text = f"{speed_data['ping']} ms"

class WiFiAnalyzerApp(App):
    """Main Application Class"""
    
    def build(self):
        Window.size = (dp(360), dp(640))  # Typical phone size
        Window.clearcolor = get_color_from_hex('#F5F5F5')
        return WiFiAnalyzerUI()
    
    def on_pause(self):
        """Handle app pause for Android"""
        return True
    
    def on_resume(self):
        """Handle app resume for Android"""
        pass

if __name__ == '__main__':
    WiFiAnalyzerApp().run()
