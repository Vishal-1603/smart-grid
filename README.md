# Smart Grid Control Dashboard

A Streamlit dashboard plus an AWS IoT publisher that simulate a household smart grid: live (or simulated) appliance power, overload detection, and automatic load shedding.

**Live path:** `iot_publisher.py` → MQTT (`smartgrid/power`) → AWS IoT Core → DynamoDB (`SmartGridData`) → `app.py`

The IoT rule that writes MQTT messages into DynamoDB is configured in AWS, not in this repo.

## Features

- Auto mode: latest DynamoDB readings, or local random simulation if AWS data is missing or stale
- Manual mode: sidebar sliders, written back to DynamoDB
- Per-device on/off, min/max failure handling, overload threshold, auto shutdown
- Tabs for dashboard, analytics, live feed, alerts, grid settings, and system info

Simulated appliances: AC, Heater, Fan, Lights, Washing Machine, Refrigerator, Microwave, TV.

## Project layout

| File | Role |
|------|------|
| `app.py` | Streamlit UI, DynamoDB read/write, grid logic |
| `iot_publisher.py` | MQTT client that publishes random device watts every 3 seconds |
| `requirements.txt` | Dashboard Python packages |
| `.streamlit/secrets.toml` | AWS keys for the app (not committed) |
| `device.pem.crt`, `private.pem.key`, `AmazonRootCA1.pem` | IoT device certificates (not committed) |
| `.devcontainer/` | GitHub Codespaces / Dev Container setup |

## Prerequisites

- Python 3.11+
- AWS account pieces (optional for local simulation UI, required for live data):
  - DynamoDB table `SmartGridData` (partition key: `timestamp`, string)
  - IAM user/keys with DynamoDB access in `ap-south-1` (or your region)
  - IoT Core thing, certificates, and a rule from topic `smartgrid/power` into DynamoDB

## Setup

```powershell
git clone https://github.com/Vishal-1603/smart-grid.git
cd smart-grid
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

Create `.streamlit/secrets.toml` (this file is gitignored):

```toml
AWS_ACCESS_KEY = "YOUR_ACCESS_KEY"
AWS_SECRET_KEY = "YOUR_SECRET_KEY"
AWS_REGION = "ap-south-1"
```

The app reads these secrets at startup. Without a valid file it will crash before the local fallback can run.

## Run the dashboard

```powershell
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

- **Auto + AWS connected:** green “Live Data” banner
- **Auto + AWS unreachable or stale:** yellow local simulation
- **Manual:** slider values are sent to DynamoDB

## Run the IoT publisher (optional)

Needs the PEM files in the project folder and extra packages not listed in `requirements.txt`:

```powershell
pip install awsiot awscrt
python iot_publisher.py
```

Endpoint, client id `SmartGridDevice`, and topic `smartgrid/power` are set in `iot_publisher.py`. Stop with Ctrl+C.

## GitHub Codespaces

This repo includes a Dev Container. Opening it in Codespaces installs `requirements.txt` and starts Streamlit on port **8501**. You still need `.streamlit/secrets.toml` (and certs if you run the publisher).

## Safety

Do not commit AWS keys, `secrets.toml`, or device certificates. Rotate any key that was ever pasted into a script or chat.
