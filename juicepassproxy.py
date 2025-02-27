import argparse
import logging
from scapy.all import *
from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import SensorInfo, Sensor

AP_DESCRIPTION = """
Juicepass Proxy - by snicker
publish Juicebox data from a UDP proxy to MQTT discoverable by HomeAssistant.
hopefully we won't need this if EnelX fixes their API!
https://github.com/home-assistant/core/issues/86588

To get the destination IP:Port of the EnelX server, telnet to your Juicenet 
device:
$ telnet 192.168.x.x 2000
and give a `list` command:
> list
> ! # Type  Info
> # 0 FILE  webapp/index.html-1.4.0.24 (1995, 0)
> # 1 UDPC  juicenet-udp-prod3-usa.enelx.com:8047 (26674)
the address is in the UDPC line- give that an nslookup or other to determine IP
juicenet-udp-prod3-usa.enelx.com - 54.161.185.130

this may change over time- but if you are using a local DNS server to reroute 
those requests to this proxy, you should stick to using the IP address here to 
avoid nameserver lookup loops.
"""

class JuiceboxMessageHandler(object):
    def __init__(self, device_name, mqtt_settings):
        self.mqtt_settings = mqtt_settings
        self.device_name = device_name
        self.entities = {
            'status': None,
            'current': None,
            'frequency': None,
            'power_lifetime': None,
            'power_session': None,
            'temperature': None,
            'voltage': None
        }
        self._init_devices()

    def _init_devices(self):
        device_info = DeviceInfo(name=self.device_name, 
                                 identifiers=self.device_name,
                                 manufacturer="EnelX")
        self._init_device_status(device_info)
        self._init_device_current(device_info)
        self._init_device_frequency(device_info)
        self._init_device_power_lifetime(device_info)
        self._init_device_power_session(device_info)
        self._init_device_temperature(device_info)
        self._init_device_voltage(device_info)

    def _init_device_status(self, device_info):
        name = "{} Status".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['status'] = sensor

    def _init_device_current(self, device_info):
        name = "{} Current".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='measurement',
                                 device_class="current",
                                 unit_of_measurement='A',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['current'] = sensor

    def _init_device_frequency(self, device_info):
        name = "{} Frequency".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='measurement',
                                 device_class="frequency",
                                 unit_of_measurement='Hz',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['frequency'] = sensor

    def _init_device_power_lifetime(self, device_info):
        name = "{} Power (Lifetime)".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='total_increasing',
                                 device_class="energy",
                                 unit_of_measurement='Wh',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['power_lifetime'] = sensor

    def _init_device_power_session(self, device_info):
        name = "{} Power (Session)".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='total_increasing',
                                 device_class="energy",
                                 unit_of_measurement='Wh',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['power_session'] = sensor

    def _init_device_temperature(self, device_info):
        name = "{} Temperature".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='measurement',
                                 device_class="temperature",
                                 unit_of_measurement='°F',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['temperature'] = sensor

    def _init_device_voltage(self, device_info):
        name = "{} Voltage".format(self.device_name)
        sensor_info = SensorInfo(name=name, unique_id=name, 
                                 state_class='measurement',
                                 device_class="voltage",
                                 unit_of_measurement='V',
                                 device=device_info)
        settings = Settings(mqtt=self.mqtt_settings, entity=sensor_info)
        sensor = Sensor(settings)
        self.entities['voltage'] = sensor

    def basic_message_try_parse(self, data):
        message = {"type": "basic"}
        message["current"] = 0
        message["power_session"] = 0
        for part in str(data).split(","):
            if part[0] == "S":
                message["status"] = {
                    "S0": "unplugged",
                    "S1": "plugged",
                    "S2": "charging",
                    "S00": "unplugged",
                    "S01": "plugged",
                    "S02": "charging",
                }.get(part)
                if message["status"] is None:
                    message["status"] = "unknown {}".format(part)
                active = (message["status"] == "charging")
            elif part[0] == "A" and active:
                message["current"] = round(float(part.split("A")[1]) * 0.1, 2)
            elif part[0] == "f":
                message["frequency"] = round(float(part.split("f")[1]) * 0.01, 2)
            elif part[0] == "L":
                message["power_lifetime"] = float(part.split("L")[1])
            elif part[0] == "E" and active:
                message["power_session"] = float(part.split("E")[1])
            elif part[0] == "T":
                message["temperature"] = round(float(part.split("T")[1]) * 1.8 + 32, 2)
            elif part[0] == "V":
                message["voltage"] = round(float(part.split("V")[1]) * 0.1, 2)
        return message

    def basic_message_publish(self, message):
        logging.debug('basic message {}'.format(message))
        try:
            for k in message:
                entity = self.entities.get(k)
                if entity:
                    entity.set_state(message.get(k))
        except:
            logging.exception('failed to publish sensor data')

    def remote_data_handler(self, data):
        logging.debug('remote: {}'.format(data))
        return data

    def local_data_handler(self, data):
        logging.debug('local : {}'.format(data))
        message = self.basic_message_try_parse(data)
        if message:
            self.basic_message_publish(message)
        return data

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=AP_DESCRIPTION)

    parser.add_argument("-j", "--juicebox", required=True, default="198.19.128.64:click,198.19.128.63:clack",
                        help="comma seperated IP:name tuples of juiceboxen")
    parser.add_argument("-i", "--interface", required=True, help="interface to listen on")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-u", "--user", type=str, help="MQTT username")
    parser.add_argument("-P", "--password", type=str, help="MQTT password")
    parser.add_argument("-H", "--host", type=str, default="127.0.0.1",
                        help="MQTT hostname to connect to (default: %(default)s)")
    parser.add_argument("-p", "--port", type=int, default=1883,
                        help="MQTT port (default: %(default)s)")
    parser.add_argument("-D", "--discovery-prefix", type=str,
                        dest="discovery_prefix",
                        default="homeassistant",
                        help="Home Assistant MQTT topic prefix (default: %(default)s)")
    # parser.add_argument("--name", type=str, default="Juicebox",
    #                     help="Home Assistant Device Name (default: %(default)s)",
    #                     dest="device_name")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    mqttsettings = Settings.MQTT(host=args.host, port=args.port,
                                 username=args.user, password=args.password,
                                 discovery_prefix=args.discovery_prefix)

    # for each configured JB, make one of these:
    boxes = args.juicebox.split(',')
    handlers = {}
    for box in boxes:
        # "198.19.1.1:pants"
        t = box.split(':')
        
        handlers[t[0]] = JuiceboxMessageHandler(mqtt_settings=mqttsettings, 
                                              device_name=t[1])
    
    # capture packets forever
    f = "udp and not dst 255.255.255 and (src 198.19.128.64 or src 198.19.128.63)" # needs to be formatted.
    while True:
        capture = sniff(iface=args.interface, filter=f, count=1)
        packet = capture[0]
        ip = packet.getlayer(IP)
        handlers[ip.src].local_data_handler(bytes(ip[UDP].payload));
                
if __name__ == '__main__':
    main()
