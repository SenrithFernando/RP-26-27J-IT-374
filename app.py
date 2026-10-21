"""SafeRide-LK Vehicle Safety Intelligence local dashboard."""

import json
import time
from pathlib import Path

import streamlit as st

from access.authorization import USERS, can_view_camera


PROJECT_ROOT = Path(__file__).resolve().parent
METRICS_FILE = PROJECT_ROOT / "data" / "live_metrics.json"
FRAME_FILE = PROJECT_ROOT / "data" / "live_frame.jpg"


def read_metrics() -> dict[str, int | float | str] | None:
    try:
        return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


st.set_page_config(page_title="SafeRide-LK | Vehicle Safety Intelligence", page_icon="🚌", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #071725; color: #eaf2f8; }
      [data-testid="stMetric"] { background: #102b42; border: 1px solid #204b6d;
        border-radius: 12px; padding: 14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚌 SafeRide-LK")
st.subheader("Vehicle Safety Intelligence")
st.caption("Live passenger monitoring for the driver and authorised parents")

with st.sidebar:
    st.header("Secure connection")
    selected_role = st.radio("Connect as", ("Administrator", "Driver", "Parent"))
    user_key = {
        "Administrator": "admin01",
        "Driver": "driver01",
        "Parent": "parent01",
    }[selected_role]
    user = USERS[user_key]
    vehicle = st.selectbox("Vehicle", ("BUS-01", "BUS-02"))
    trip_active = st.toggle("Trip active", value=True)
    camera_source = st.text_input("Camera source", value="0")
    st.code(f"python camera/pose.py --source {camera_source}", language="bash")
    st.caption("Prototype access control. A real deployment needs secure account login and video streaming.")

allowed = can_view_camera(user, vehicle, trip_active)
connection, privacy = st.columns((2, 3))
with connection:
    st.write(f"**Connected as:** {user['name']}")
    st.write(f"**Role:** {user['role'].title()}")
    st.write(f"**Requested vehicle:** {vehicle}")
with privacy:
    if allowed:
        st.success("Camera access authorised for this active trip")
    elif not trip_active:
        st.warning("Camera unavailable: this trip is not active")
    else:
        st.error("Camera access denied: this user is not assigned to the selected vehicle")


@st.fragment(run_every="1s")
def live_vehicle_dashboard() -> None:
    """Refresh the local camera preview and safety metrics every second."""
    if not allowed:
        st.info("Live camera and passenger details are hidden until access is authorised.")
        return

    metrics = read_metrics()
    if metrics is None:
        st.warning("Waiting for camera analysis. Start the command shown in the sidebar.")
        return

    age_seconds = time.time() - float(metrics.get("updated_at", 0))
    if age_seconds > 5:
        st.warning("Camera data is stale. Check that camera/pose.py is running.")
    else:
        st.success(f"Live camera connected — source {metrics.get('source', 'unknown')}")

    total = int(metrics.get("total_passengers", 0))
    sitting = int(metrics.get("sitting", 0))
    standing = int(metrics.get("standing", 0))
    walking = int(metrics.get("walking", 0))
    unclear = int(metrics.get("pose_unclear", 0))

    camera_column, details_column = st.columns((3, 2))
    with camera_column:
        st.subheader("Live bus camera")
        if FRAME_FILE.exists():
            st.image(str(FRAME_FILE), width="stretch")
        else:
            st.info("Camera preview will appear after the analyzer receives its first frame.")

    with details_column:
        st.subheader("Passenger details")
        first_row = st.columns(2)
        first_row[0].metric("Total passengers", total)
        first_row[1].metric("Sitting", sitting)
        second_row = st.columns(2)
        second_row[0].metric("Standing", standing)
        second_row[1].metric("Walking", walking)
        st.metric("Pose unclear", unclear)

        active_passengers = standing + walking
        if total == 0:
            st.info("No passengers detected")
        elif active_passengers >= 4:
            st.error("HIGH RISK — many active passengers")
        elif active_passengers >= 2:
            st.warning("MODERATE RISK — monitor standing passengers")
        else:
            st.success("LOW RISK — normal passenger activity")

    st.subheader("Passenger behaviour summary")
    st.bar_chart({"Count": {"Sitting": sitting, "Standing": standing, "Walking": walking}})
    st.caption("Pose unclear means the camera cannot see enough leg keypoints to classify a passenger safely.")


live_vehicle_dashboard()
