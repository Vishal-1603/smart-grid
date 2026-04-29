import json, time, random
from awscrt import mqtt
from awsiot import mqtt_connection_builder

ENDPOINT = "a2oveyteuykdbr-ats.iot.ap-south-1.amazonaws.com"
CLIENT_ID = "SmartGridDevice"
TOPIC = "smartgrid/power"

devices = {
    "AC": (1000, 2000),
    "Heater": (1200, 2500),
    "Fan": (50, 200),
    "Lights": (50, 400),
    "Washing Machine": (500, 1200),
    "Refrigerator": (150, 600),
    "Microwave": (800, 1500)
}

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath="device.pem.crt",
    pri_key_filepath="private.pem.key",
    ca_filepath="AmazonRootCA1.pem",
    client_id=CLIENT_ID,
)

connect_future = mqtt_connection.connect()
connect_future.result()
print("✅ Connected to AWS IoT Core!")

try:
    while True:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "devices": {
                d: round(random.uniform(lo, hi), 2)
                for d, (lo, hi) in devices.items()
            }
        }
        mqtt_connection.publish(
            topic=TOPIC,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        print(f"📡 Published: {payload}")
        time.sleep(3)
except KeyboardInterrupt:
    print("\n🛑 Stopped publishing.")