import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, time, datetime, timedelta
from streamlit_calendar import calendar

# --- PAGE CONFIG ---
st.set_page_config(page_title="Nachbarn in Thailand", page_icon="🗓️", layout="wide")
st.markdown(
    """
    <h1 style="display:flex;align-items:center;gap:10px;margin:0;">
      <img src="https://upload.wikimedia.org/wikipedia/commons/a/a9/Flag_of_Thailand.svg"
           width="32" height="20" alt="TH flag" style="border-radius:2px;">
      Nachbarn in Thailand
    </h1>
    """,
    unsafe_allow_html=True,
)


# ============== PASSWORD GATE ==============
def check_password() -> bool:
    if "auth_ok" in st.session_state and st.session_state.auth_ok:
        return True

    secret_pwd = (st.secrets.get("app_password", "") or "").strip()

    with st.form("login_form", clear_on_submit=False):
        st.subheader("🔒 Enter password to continue")
        pwd = st.text_input("Password", type="password")
        login = st.form_submit_button("Log in", use_container_width=True)

    if login:
        if not secret_pwd:
            st.error("Server misconfigured: app_password is missing in secrets.toml.")
            st.stop()
        if (pwd or "").strip() == secret_pwd:
            st.session_state.auth_ok = True
            st.success("Access granted ✅")
            st.rerun()
        else:
            st.error("Incorrect password. Try again.")
    return False

if not check_password():
    st.stop()
# ===========================================

# --- GOOGLE SHEETS AUTH ---
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
client = gspread.authorize(creds)
SHEET_ID = st.secrets["sheet_id"]
WORKSHEET_NAME = st.secrets["worksheet_name"]
sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

# --- HEADERS ---
COLUMNS = ["Start date", "Start time", "End date", "End time", "Activity", "Notes", "Participants"]

def ensure_headers():
    headers = sheet.row_values(1)
    cleaned = [h.strip() for h in headers if h.strip() != ""]
    if len(cleaned) != len(COLUMNS) or set(h.lower() for h in cleaned) != set(h.lower() for h in COLUMNS):
        sheet.update("A1:G1", [COLUMNS])

def load_data() -> pd.DataFrame:
    ensure_headers()
    records = sheet.get_all_records(expected_headers=COLUMNS, default_blank="")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["Start date", "Start time"], kind="stable").reset_index(drop=True)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df[COLUMNS]

def update_row(row_number: int, new_values: list[str]):
    sheet.update(f"A{row_number}:G{row_number}", [new_values])

def delete_row(row_number: int):
    sheet.delete_rows(row_number)

def append_row(values: list[str]):
    sheet.append_row(values)

df = load_data()

# --- PEOPLE & COLORS ---
PEOPLE = ["All", "Eve", "Jari", "Maja", "Stijn"]
PERSON_COLORS = {
    "All":   {"bg": "#90CAF9", "border": "#1E88E5", "text": "#0D47A1"},
    "Eve":   {"bg": "#EF9A9A", "border": "#E53935", "text": "#B71C1C"},
    "Jari":  {"bg": "#A5D6A7", "border": "#43A047", "text": "#1B5E20"},
    "Maja":  {"bg": "#F48FB1", "border": "#EC407A", "text": "#880E4F"},
    "Stijn": {"bg": "#FFF59D", "border": "#FDD835", "text": "#F57F17"},
}
COMBO_COLOR = {"bg": "#FFCC80", "border": "#FB8C00", "text": "#E65100"}
DEFAULT_COLOR = {"bg": "#ECEFF1", "border": "#B0BEC5", "text": "#263238"}

def parse_participants(cell: str) -> list[str]:
    if not cell:
        return []
    return [p.strip() for p in str(cell).split(",") if p.strip()]

def join_participants(parts: list[str]) -> str:
    return ", ".join(parts)

def pick_color_for(parts: list[str]) -> dict:
    if len(parts) >= 2:
        return COMBO_COLOR
    if len(parts) == 1:
        return PERSON_COLORS.get(parts[0], DEFAULT_COLOR)
    return DEFAULT_COLOR

# --- INIT ADD-FORM STATE (so it only clears on success) ---
def _ensure_form_state():
    st.session_state.setdefault("add_start_date", date.today())
    st.session_state.setdefault("add_start_time", time(9, 0))
    st.session_state.setdefault("add_end_date", date.today())
    st.session_state.setdefault("add_end_time", time(10, 0))
    st.session_state.setdefault("add_activity", "")
    st.session_state.setdefault("add_notes", "")
    st.session_state.setdefault("add_participants", ["All"])

def _reset_form_state():
    st.session_state["add_start_date"] = date.today()
    st.session_state["add_start_time"] = time(9, 0)
    st.session_state["add_end_date"] = date.today()
    st.session_state["add_end_time"] = time(10, 0)
    st.session_state["add_activity"] = ""
    st.session_state["add_notes"] = ""
    st.session_state["add_participants"] = ["All"]

_ensure_form_state()

# --- LAYOUT ---
left, right = st.columns([1, 2])

# --- ADD ACTIVITY ---
with left:
    st.header("➕ Add activity")
    # clear_on_submit=False → velden blijven staan bij validatiefout
    with st.form("add_form", clear_on_submit=False):
        start_date = st.date_input("Start date", value=st.session_state["add_start_date"])
        start_time = st.time_input("Start time", value=st.session_state["add_start_time"], step=timedelta(minutes=15))
        end_date   = st.date_input("End date", value=st.session_state["add_end_date"])
        end_time   = st.time_input("End time", value=st.session_state["add_end_time"], step=timedelta(minutes=15))
        activity   = st.text_input("Activity", value=st.session_state["add_activity"], placeholder="Activity")
        participants = st.multiselect("Participants", PEOPLE, default=st.session_state["add_participants"])
        notes      = st.text_area("Notes (optional)", value=st.session_state["add_notes"], height=80)
        submitted  = st.form_submit_button("Add Activity", use_container_width=True)

    if submitted:
        # schrijf huidige invoer terug naar state (bij validatiefout blijft alles staan)
        st.session_state["add_start_date"] = start_date
        st.session_state["add_start_time"] = start_time
        st.session_state["add_end_date"]   = end_date
        st.session_state["add_end_time"]   = end_time
        st.session_state["add_activity"]   = activity
        st.session_state["add_notes"]      = notes
        st.session_state["add_participants"] = participants

        if not activity.strip():
            st.warning("Please enter an activity name.")
        else:
            append_row([
                start_date.isoformat(),
                start_time.strftime("%H:%M"),
                end_date.isoformat(),
                end_time.strftime("%H:%M"),
                activity.strip(),
                notes.strip(),
                join_participants(participants),
            ])
            st.success("✅ Activity added successfully!")
            # nu pas écht leegmaken
            _reset_form_state()
            st.rerun()

# --- CALENDAR ---
with right:
    st.header("📆 Schedule")

    def to_iso(d, t):
        if not d:
            return None
        t = t or "00:00"
        try:
            return datetime.fromisoformat(f"{d} {t}").isoformat()
        except Exception:
            # fallback
            try:
                ts = pd.to_datetime(f"{d} {t}")
                return ts.isoformat()
            except Exception:
                return None

    events = []
    for i, r in df.iterrows():
        sheet_row = i + 2
        start_iso = to_iso(str(r["Start date"]), r["Start time"])
        end_iso   = to_iso(str(r["End date"]), r["End time"])
        if not start_iso:
            continue
        parts = parse_participants(r.get("Participants", ""))
        colors = pick_color_for(parts)
        who = " & ".join(parts) if parts else ""
        title = f"{r['Activity']} • {who}" if who else (r["Activity"] or "Activity")
        events.append({
            "id": str(sheet_row),
            "title": title,
            "start": start_iso,
            "end": end_iso or None,
            "backgroundColor": colors["bg"],
            "borderColor": colors["border"],
            "textColor": colors["text"],
            "extendedProps": {"notes": r["Notes"], "participants": parts}
        })

    state = calendar(
        events=events,
        options={
            "initialView": "timeGridWeek",
            "locale": "en-gb",
            "firstDay": 1,
            "slotMinTime": "00:00:00",
            "slotMaxTime": "24:00:00",
            "slotDuration": "01:00:00",     # visueel per uur
            "snapDuration": "00:15:00",     # slepen/resize per kwartier
            "allDaySlot": False,
            "nowIndicator": True,
            "height": "auto",               # ← fix voor “dikke laatste rij”
            "expandRows": False,            # ← idem
            "editable": True,
            "eventResizableFromStart": True,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "timeGridDay,timeGridWeek,dayGridMonth,listWeek"
            },
            "slotLabelFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
            "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
        },
        key="calendar"
    )

# --- DRAG/DROP / RESIZE → OPSLAAN ---
def handle_update(event):
    event_id = int(event["id"])
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"]) if event.get("end") else start + timedelta(hours=1)
    cur = df.iloc[event_id - 2]
    update_row(event_id, [
        start.date().isoformat(),
        start.strftime("%H:%M"),
        end.date().isoformat(),
        end.strftime("%H:%M"),
        cur["Activity"],
        cur["Notes"],
        cur.get("Participants", ""),
    ])

if state:
    for key in ("eventChange", "eventDrop", "eventResize"):
        if key in state and state[key]:
            handle_update(state[key]["event"])
            st.toast("🕒 Event updated")
            st.rerun()

# --- EVENT CLICK (EDIT) ---
if state and "eventClick" in state:
    eid = int(state["eventClick"]["event"]["id"])
    record = df.iloc[eid - 2]
    st.session_state["edit_record"] = record
    st.session_state["edit_row"] = eid
    st.session_state["open_edit"] = True

if st.session_state.get("open_edit", False):
    rec = st.session_state["edit_record"]
    row = st.session_state["edit_row"]
    st.subheader(f"✏️ Edit Activity: {rec['Activity']}")

    with st.form("edit_form", clear_on_submit=False):
        start_date = st.date_input("Start date", value=pd.to_datetime(rec["Start date"]).date())
        start_time = st.time_input("Start time", value=datetime.strptime(rec["Start time"], "%H:%M").time(), step=timedelta(minutes=15))
        end_date   = st.date_input("End date", value=pd.to_datetime(rec["End date"]).date())
        end_time   = st.time_input("End time", value=datetime.strptime(rec["End time"], "%H:%M").time(), step=timedelta(minutes=15))
        activity   = st.text_input("Activity", value=rec["Activity"])
        participants = st.multiselect("Participants", PEOPLE, default=parse_participants(rec.get("Participants", "")) or ["All"])
        notes      = st.text_area("Notes", value=rec["Notes"], height=80)
        c1, c2, c3 = st.columns(3)
        save = c1.form_submit_button("💾 Save", use_container_width=True)
        delete = c2.form_submit_button("🗑️ Delete", use_container_width=True)
        cancel = c3.form_submit_button("Cancel", use_container_width=True)

    if save:
        update_row(row, [
            start_date.isoformat(),
            start_time.strftime("%H:%M"),
            end_date.isoformat(),
            end_time.strftime("%H:%M"),
            activity.strip(),
            notes.strip(),
            join_participants(participants),
        ])
        st.session_state["open_edit"] = False
        st.success("✅ Activity updated successfully!")
        st.rerun()
    if delete:
        delete_row(row)
        st.session_state["open_edit"] = False
        st.success("🗑️ Activity deleted.")
        st.rerun()
    if cancel:
        st.session_state["open_edit"] = False
        st.info("Edit canceled.")
