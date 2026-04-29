import streamlit as st
import random
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import boto3

st.set_page_config(page_title="Smart Grid Pro Dashboard", layout="wide")

st.title("⚡ Smart Grid Professional Control System")

# ---------- AWS CONFIG ----------
AWS_ACCESS_KEY = st.secrets["AWS_ACCESS_KEY"]
AWS_SECRET_KEY = st.secrets["AWS_SECRET_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]

# ---------- FETCH AWS DATA (with freshness check) ----------
@st.cache_data(ttl=3)
def fetch_latest_data():
    try:
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        table = dynamodb.Table('SmartGridData')
        response = table.scan()
        items = response.get('Items', [])

        valid_items = [i for i in items if 'payload' in i and 'devices' in i['payload']]

        if valid_items:
            valid_items.sort(key=lambda x: x.get('timestamp', ''))
            latest = valid_items[-1]
            latest_timestamp = latest.get('timestamp', '')

            if latest_timestamp:
                data_time = datetime.fromisoformat(latest_timestamp)
                now_time = datetime.now()
                age_seconds = (now_time - data_time).total_seconds()

                if age_seconds > 10:
                    return None

            return {k: float(v) for k, v in latest['payload']['devices'].items()}

    except Exception as e:
        st.warning(f"AWS fetch failed: {e}")
    return None

# ---------- SEND MANUAL DATA TO DYNAMODB ----------
def send_manual_to_dynamodb(device_power):
    try:
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        table = dynamodb.Table('SmartGridData')
        table.put_item(Item={
            'timestamp': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            'payload': {
                'devices': {k: str(v) for k, v in device_power.items()},
                'timestamp': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                'source': 'manual'
            }
        })
    except Exception as e:
        st.warning(f"Failed to send manual data to AWS: {e}")

# ---------- DEVICE CONFIG ----------
devices = {
    "AC": {"base": 1500, "min": 1000, "max": 2000},
    "Heater": {"base": 2000, "min": 1200, "max": 2500},
    "Fan": {"base": 100, "min": 50, "max": 200},
    "Lights": {"base": 200, "min": 50, "max": 400},
    "Washing Machine": {"base": 800, "min": 500, "max": 1200},
    "Refrigerator": {"base": 300, "min": 150, "max": 600},
    "Microwave": {"base": 1200, "min": 800, "max": 1500}
}

# ---------- SESSION ----------
if "history" not in st.session_state:
    st.session_state.history = []
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "device_states" not in st.session_state:
    st.session_state.device_states = {d: True for d in devices}
if "manual_values" not in st.session_state:
    st.session_state.manual_values = {d: devices[d]["base"] for d in devices}
if "mode" not in st.session_state:
    st.session_state.mode = "Auto"
if "threshold_ratio" not in st.session_state:
    st.session_state.threshold_ratio = 0.8
if "auto_shutdown" not in st.session_state:
    st.session_state.auto_shutdown = True
if "feed_log" not in st.session_state:
    st.session_state.feed_log = []

# ---------- GRID CAPACITY ----------
MAX_TOTAL_CAPACITY = sum(d["max"] for d in devices.values())
OVERLOAD_THRESHOLD = MAX_TOTAL_CAPACITY * st.session_state.threshold_ratio

# ---------- SIDEBAR ----------
st.sidebar.header("🎮 Device Control Panel")
st.session_state.mode = st.sidebar.radio("Mode", ["Auto", "Manual"])
st.session_state.auto_shutdown = st.sidebar.checkbox(
    "Enable Auto Shutdown", value=st.session_state.auto_shutdown
)
st.sidebar.markdown("---")

for d in devices:
    st.session_state.device_states[d] = st.sidebar.toggle(d, st.session_state.device_states[d])
    if st.session_state.mode == "Manual":
        st.session_state.manual_values[d] = st.sidebar.slider(
            f"{d} Power (W)",
            0,
            int(devices[d]["max"] + 500),
            int(st.session_state.manual_values[d]),
            key=f"{d}_slider"
        )

st.sidebar.markdown("---")
st.sidebar.write(f"⚡ Max Capacity: {int(MAX_TOTAL_CAPACITY)} W")
st.sidebar.write(f"⚠️ Overload Limit: {int(OVERLOAD_THRESHOLD)} W")

# ---------- FETCH AWS DATA ----------
aws_data = fetch_latest_data()

if st.session_state.mode == "Manual":
    st.info("🔧 Manual Mode: Using slider values → Sending to AWS DynamoDB")
elif aws_data:
    st.success("🟢 Live Data: AWS IoT Core → DynamoDB")
else:
    st.warning("🟡 Fallback: Local Simulation (AWS not connected)")

# ---------- POWER CALC ----------
device_power = {}
device_status = {}
total_power = 0
current_feed = []  # collect data source messages for this cycle

for d, active in st.session_state.device_states.items():
    if not active:
        power = 0
        status = "OFF 🔌"
    else:
        if st.session_state.mode == "Auto":
            if aws_data and d in aws_data:
                power = float(aws_data[d])
                current_feed.append({"time": datetime.now().strftime("%H:%M:%S"), "source": "☁️ AWS", "device": d, "power": f"{power:.2f}W"})
            else:
                power = devices[d]["base"] * random.uniform(0.7, 1.3)
                current_feed.append({"time": datetime.now().strftime("%H:%M:%S"), "source": "🟡 Simulated", "device": d, "power": f"{power:.2f}W"})
        else:
            power = st.session_state.manual_values[d]
            current_feed.append({"time": datetime.now().strftime("%H:%M:%S"), "source": "🔧 Manual", "device": d, "power": f"{power:.2f}W"})

        if power < devices[d]["min"]:
            power = 0
            status = "OFF (Low Power)"
        elif power > devices[d]["max"]:
            power = 0
            status = "FAILED 🔴"
            st.session_state.alerts.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"{d} FAILED (exceeded {devices[d]['max']}W)",
                "grid_status": "Device Failure"
            })
        else:
            status = "ON 🟢"

    device_power[d] = round(power, 2)
    device_status[d] = status
    total_power += power

if st.session_state.mode == "Manual":
    send_manual_to_dynamodb(device_power)

# Save feed log (keep last 50 entries to avoid memory buildup)
st.session_state.feed_log = (current_feed + st.session_state.feed_log)[:50]

# ---------- GRID STATUS ----------
grid_status = "🟢 Normal"

if total_power > OVERLOAD_THRESHOLD:
    grid_status = "🔴 OVERLOAD"
    st.session_state.alerts.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": f"GRID OVERLOAD ({round(total_power,2)}W)",
        "grid_status": "OVERLOAD"
    })

# ---------- AUTO SHUTDOWN ----------
if grid_status == "🔴 OVERLOAD" and st.session_state.auto_shutdown:
    sorted_devices = sorted(device_power.items(), key=lambda x: x[1], reverse=True)
    for d, power in sorted_devices:
        if total_power <= OVERLOAD_THRESHOLD:
            break
        if power > 0:
            total_power -= power
            device_power[d] = 0
            device_status[d] = "SHUTDOWN ⚠️"
            st.session_state.alerts.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"AUTO SHUTDOWN: {d} turned off to reduce load",
                "grid_status": "CONTROLLED"
            })
    grid_status = "🟡 Controlled"

# ---------- USAGE ----------
usage_percent = (total_power / MAX_TOTAL_CAPACITY) * 100

# ---------- SAVE HISTORY ----------
now = datetime.now().strftime("%H:%M:%S")
st.session_state.history.append({
    "time": now,
    "total": total_power,
    **device_power
})

df = pd.DataFrame(st.session_state.history)
df_devices = pd.DataFrame(device_power.items(), columns=["Device", "Power"])

# ---------- TABS ----------
tabs = st.tabs([
    "🏠 Dashboard",
    "📊 Analytics",
    "📡 Live Feed",
    "🚨 Alerts",
    "⚡ Grid Settings",
    "ℹ️ System Info"
])

# ================= DASHBOARD =================
with tabs[0]:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⚡ Total Power", round(total_power, 2))
    col2.metric("📊 Usage %", f"{usage_percent:.1f}%")
    col3.metric("🔌 Active Devices", sum(v > 0 for v in device_power.values()))
    col4.metric("🚨 Grid Status", grid_status)

    st.progress(min(int(usage_percent), 100))

    st.plotly_chart(px.bar(df_devices, x="Device", y="Power", color="Device"),
                    use_container_width=True, key="bar_dash")
    st.plotly_chart(px.pie(df_devices, names="Device", values="Power", hole=0.5),
                    use_container_width=True, key="donut_dash")
    st.plotly_chart(px.line(df, x="time", y="total"),
                    use_container_width=True, key="line_dash")

    st.subheader("📄 Device Status")
    st.dataframe(pd.DataFrame({
        "Device": list(device_status.keys()),
        "Status": list(device_status.values()),
        "Power (W)": list(device_power.values())
    }))

# ================= ANALYTICS =================
with tabs[1]:
    st.subheader("📊 Per Device Power Trends")
    for d in devices:
        if d in df.columns:
            st.plotly_chart(px.line(df, x="time", y=d, title=f"{d} Power Trend"),
                            use_container_width=True, key=f"{d}_trend")

# ================= LIVE FEED =================
with tabs[2]:
    st.subheader("📡 Live Data Source Feed")
    st.caption("Real-time log showing where each device's power reading is coming from")
    if st.session_state.feed_log:
        df_feed = pd.DataFrame(st.session_state.feed_log)
        st.dataframe(df_feed, use_container_width=True, hide_index=True)
    else:
        st.info("No data received yet. Waiting for first cycle...")

# ================= ALERTS =================
with tabs[3]:
    st.subheader("🚨 Smart Alerts")
    if st.session_state.alerts:
        st.dataframe(pd.DataFrame(st.session_state.alerts))
    else:
        st.success("No alerts")

# ================= GRID SETTINGS =================
with tabs[4]:
    st.session_state.threshold_ratio = st.slider(
        "Overload Threshold (% of max capacity)",
        0.5, 1.0, st.session_state.threshold_ratio
    )
    st.write(f"Max Capacity: {int(MAX_TOTAL_CAPACITY)} W")
    st.write(f"Overload Threshold: {int(OVERLOAD_THRESHOLD)} W")

# ================= SYSTEM INFO =================
with tabs[5]:
    st.write("### Smart Grid System")
    st.write("""
    - Multi-device smart grid simulation
    - Dynamic overload detection
    - Multi-level automatic load shedding
    - Device failure handling
    - Real-time analytics dashboard
    - ☁️ AWS IoT Core integration (MQTT)
    - 🗄️ DynamoDB cloud storage
    - 📡 Real-time data from IoT publisher
    - 🔧 Manual mode with AWS sync
    """)

# ---------- REFRESH ----------
time.sleep(1)
st.rerun()