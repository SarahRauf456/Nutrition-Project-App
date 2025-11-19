# app.py - Full working Nutrition App (single-file)
import streamlit as st
import sqlite3
import os
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import random
import string
import plotly.express as px
import textwrap

# -------------------- CONFIG --------------------
APP_TITLE = "Nutrition App — AI Health & Nutrition Analyzer (Offline)"
DB_DIR = "data"
DB_FILENAME = "nutriapp.db"
DB_PATH = os.path.join(DB_DIR, DB_FILENAME)
ADMIN_EMAILS = ["nehathegreat702@gmail.com"]  # change or keep empty for no admin
MAGIC_CODE_TTL_MIN = 15
DEBUG = True  # set False to hide debug prints and codes

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")

# -------------------- DB SETUP --------------------
os.makedirs(DB_DIR, exist_ok=True)
# Print absolute path so you can confirm the runtime DB location
if DEBUG:
    st.write("USING DATABASE FILE AT:", os.path.abspath(DB_PATH))

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Ensure auth_codes table has created_at column (migrate if needed)
cur.executescript("""
CREATE TABLE IF NOT EXISTS users(
    email TEXT PRIMARY KEY,
    name TEXT,
    dob TEXT,
    height_cm REAL,
    weight_kg REAL,
    gender TEXT,
    activity_level TEXT,
    goals TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    code TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS water_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    ml INTEGER,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS meals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    meal_name TEXT,
    calories REAL,
    protein REAL,
    carbs REAL,
    fat REAL,
    notes TEXT,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS exercises(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    category TEXT,
    name TEXT,
    duration_min INTEGER,
    calories_burned REAL,
    notes TEXT,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS sleep_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    date TEXT,
    hours REAL
);

CREATE TABLE IF NOT EXISTS habits(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    habit TEXT,
    last_completed TEXT,
    streak INTEGER DEFAULT 0
);
""")
conn.commit()

# If the auth_codes table existed previously without created_at, try to add it
cols = [c[1] for c in cur.execute("PRAGMA table_info(auth_codes)").fetchall()]
if "created_at" not in cols:
    try:
        cur.execute("ALTER TABLE auth_codes ADD COLUMN created_at TEXT")
        conn.commit()
        if DEBUG:
            st.write("DEBUG: Added created_at column to auth_codes")
    except Exception as e:
        # If alter fails for some reason, print but continue
        if DEBUG:
            st.write("DEBUG: Could not ALTER auth_codes:", e)

# -------------------- UTILITIES --------------------
def insert_and_commit(query, params=()):
    try:
        cur.execute(query, params)
        conn.commit()
    except Exception as e:
        st.error(f"SQL ERROR: {e}")
        raise

def query_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

def gen_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def now_iso():
    # SQLite-friendly timestamp format (no T, seconds precision)
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def prune_expired_codes(ttl_minutes=MAGIC_CODE_TTL_MIN):
    # Deletes codes older than TTL — run AFTER verification or periodically
    cutoff = (datetime.utcnow() - timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("DELETE FROM auth_codes WHERE created_at < ?", (cutoff,))
    conn.commit()

def verify_code(email, code):
    """
    Return True if there's a matching code for email that was created within TTL.
    Does not prune BEFORE checking.
    """
    cutoff = (datetime.utcnow() - timedelta(minutes=MAGIC_CODE_TTL_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    row = cur.execute("""
        SELECT 1 FROM auth_codes
        WHERE email = ? AND code = ? AND created_at >= ?
        ORDER BY created_at DESC LIMIT 1
    """, (email, code, cutoff)).fetchone()
    return row is not None

# Optional: debug helper to show current auth codes (for development only)
def debug_show_codes():
    if DEBUG:
        rows = cur.execute("SELECT email, code, created_at FROM auth_codes ORDER BY created_at DESC LIMIT 20").fetchall()
        st.sidebar.write("DEBUG CODES (recent):", rows)

# -------------------- SMALL FOOD DB (offline) --------------------
FOOD_DB = {
    "oatmeal": {"cal": 150, "protein": 5, "carbs": 27, "fat": 3},
    "banana": {"cal": 105, "protein": 1.3, "carbs": 27, "fat": 0.4},
    "apple": {"cal": 95, "protein": 0.5, "carbs": 25, "fat": 0.3},
    "grilled chicken": {"cal": 220, "protein": 40, "carbs": 0, "fat": 6},
    "salmon": {"cal": 350, "protein": 34, "carbs": 0, "fat": 22},
    "lentil stew": {"cal": 310, "protein": 18, "carbs": 45, "fat": 4},
    "greek yogurt": {"cal": 140, "protein": 12, "carbs": 10, "fat": 5},
    "rice (1 cup cooked)": {"cal": 205, "protein": 4.3, "carbs": 45, "fat": 0.4},
    "egg (large)": {"cal": 78, "protein": 6, "carbs": 0.6, "fat": 5},
    "tofu (100g)": {"cal": 76, "protein": 8, "carbs": 1.9, "fat": 4.8},
    "protein shake": {"cal": 200, "protein": 25, "carbs": 8, "fat": 3},
    "salad (veg)": {"cal": 120, "protein": 3, "carbs": 10, "fat": 8},
}

# -------------------- CANNED QA & EXERCISES --------------------
EXERCISES = {
    "Hands": [
        {"name": "Push-ups", "desc": "Bodyweight exercise for chest/triceps/shoulders.", "img": ""},
        {"name": "Bicep Curls", "desc": "Dumbbell curls for biceps.", "img": ""},
    ],
    "Legs": [
        {"name": "Squats", "desc": "Quad & glute-builder. Keep knees aligned.", "img": ""},
        {"name": "Lunges", "desc": "Balance & unilateral strength.", "img": ""},
    ],
    "Core": [
        {"name": "Plank", "desc": "Hold straight bodyline for core stability.", "img": ""},
        {"name": "Russian Twist", "desc": "Rotational core exercise.", "img": ""},
    ],
    "Back": [
        {"name": "Superman", "desc": "Back-extension to target lower back.", "img": ""},
        {"name": "Bent-over Row", "desc": "Rowing motion to strengthen back.", "img": ""},
    ],
    "Full-body": [
        {"name": "Burpees", "desc": "High-intensity full-body movement.", "img": ""},
        {"name": "Kettlebell Swing", "desc": "Hip hinge power movement.", "img": ""},
    ],
}

CANNED_QA = {
    "how much protein": "Aim for ~1.2-2.0 g/kg of body weight per day if active. Spread it across meals.",
    "how many calories": "Calories depend on BMR and activity. Use Profile to estimate—balance energy in vs out.",
    "what to eat for breakfast": "Oats with fruit + protein (yogurt or egg) is a balanced start.",
    "how much water": "Aim ~2000–3000 ml/day, more if active or hot. Log water in Hydration tab.",
    "post workout meal": "Combining protein + carbs helps recovery (e.g., chicken + rice or protein shake + banana).",
    "how to lose weight": "Mild calorie deficit, prioritize protein & strength training, sleep, hydration, and consistency.",
    "how to gain muscle": "Progressive overload resistance training + 1.6–2.2 g/kg protein and slight calorie surplus.",
}

# -------------------- SESSION STATE --------------------
if "email" not in st.session_state:
    st.session_state.email = ""
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "just_sent_code" not in st.session_state:
    st.session_state.just_sent_code = False
if "shown_code" not in st.session_state:
    st.session_state.shown_code = None

# -------------------- AUTH UI --------------------
st.sidebar.markdown("---")
st.sidebar.header("Login (magic code)")

def send_code_flow(email_in):
    email_in = (email_in or "").strip().lower()
    if not email_in:
        st.sidebar.error("Enter an email")
        return
    # generate
    code = gen_code(6)
    ts = now_iso()
    # insert
    insert_and_commit("INSERT INTO auth_codes(email, code, created_at) VALUES (?, ?, ?)", (email_in, code, ts))
    st.session_state.just_sent_code = True
    st.session_state.shown_code = code
    # show
    st.sidebar.success(f"Magic code generated (expires in {MAGIC_CODE_TTL_MIN} minutes)")
    if DEBUG:
        st.sidebar.info(f"DEBUG CODE: {code}")
    # debug list
    debug_show_codes()

def verify_flow(email_in, code_in):
    email_in = (email_in or "").strip().lower()
    code_in = (code_in or "").strip()
    if not email_in or not code_in:
        st.sidebar.error("Enter email and code")
        return
    # verify (does NOT prune before verify)
    if verify_code(email_in, code_in):
        # success: set session and remove used codes for this email to prevent reuse
        st.session_state.logged_in = True
        st.session_state.email = email_in
        # delete codes for that email (used ones)
        cur.execute("DELETE FROM auth_codes WHERE email = ?", (email_in,))
        conn.commit()
        st.sidebar.success("Verified — logged in")
    else:
        st.sidebar.error("Invalid or expired code")
    # tidy expired codes after check
    prune_expired_codes(MAGIC_CODE_TTL_MIN)

with st.sidebar.form("auth_form"):
    if not st.session_state.logged_in:
        email_input = st.text_input("Email", value=st.session_state.email or "")
        col1, col2 = st.columns([1,1])
        with col1:
            st.form_submit_button("Send code", on_click=lambda: send_code_flow(email_input))
        with col2:
            code_input = st.text_input("Enter code")
            st.form_submit_button("Verify", on_click=lambda: verify_flow(email_input, code_input))
    else:
        st.markdown(f"**Logged in as:** {st.session_state.email}")
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.email = ""
            st.experimental_rerun()

# expose to main app
email = st.session_state.email
is_admin = (email in ADMIN_EMAILS) if email else False

# -------------------- NAVIGATION --------------------
st.sidebar.markdown("---")
page = st.sidebar.selectbox("Open", [
    "Dashboard", "Profile", "Hydration", "Nutrition", "Exercises",
    "Sleep & Habits", "Diet Generator", "Medical Advisor", "AI Chatbot", "Admin"
])

# -------------------- PAGES (Profile, Hydration, Nutrition, etc.) --------------------
# For brevity I'll attach simple working implementations similar to your previous layout.
# You can paste the rest of your UI here; below are the main sections already implemented.

if page == "Profile":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Profile — Manage your info")
        row_df = query_df("SELECT * FROM users WHERE email=?", (email,))
        row = row_df.iloc[0].to_dict() if not row_df.empty else {}
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name", value=row.get("name", ""))
            dob_val = row.get("dob", "")
            dob = st.date_input("Date of birth", value=datetime.strptime(dob_val, "%Y-%m-%d").date() if dob_val else date(1990,1,1))
            gender = st.selectbox("Gender", ["male", "female", "other"], index=0 if row.get("gender","male").lower().startswith("m") else 1)
        with col2:
            height_cm = st.number_input("Height (cm)", value=float(row.get("height_cm") or 170.0))
            weight_kg = st.number_input("Weight (kg)", value=float(row.get("weight_kg") or 70.0))
            activity = st.selectbox("Activity level", ["sedentary","light","moderate","active","very active"], index=2)
            goals = st.text_input("Goals", value=row.get("goals","maintain"))
        if st.button("Save profile"):
            insert_and_commit(
                """INSERT OR REPLACE INTO users(email,name,dob,height_cm,weight_kg,gender,activity_level,goals,created_at)
                   VALUES(?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM users WHERE email=?),?))""",
                (email, name, dob.isoformat(), height_cm, weight_kg, gender, activity, goals, email, now_iso())
            )
            st.success("Profile saved")

elif page == "Hydration":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Hydration")
        col1, col2 = st.columns([2,1])
        with col1:
            add_ml = st.number_input("Add water (ml)", min_value=50, max_value=5000, value=250, step=50)
            if st.button("Log water"):
                insert_and_commit("INSERT INTO water_logs(email,ml,timestamp) VALUES(?,?,?)", (email, int(add_ml), now_iso()))
                st.success(f"Logged {add_ml} ml")
        with col2:
            last = query_df("SELECT timestamp, ml FROM water_logs WHERE email=? ORDER BY timestamp DESC LIMIT 10", (email,))
            if not last.empty:
                st.write("Recent logs")
                st.dataframe(last)
        all_df = query_df("SELECT timestamp, ml FROM water_logs WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
        if not all_df.empty:
            all_df['timestamp'] = pd.to_datetime(all_df['timestamp'])
            daily = all_df.groupby(all_df['timestamp'].dt.date)['ml'].sum().reset_index()
            daily.columns = ['date','ml']
            fig = px.bar(daily, x='date', y='ml', title="Daily water (ml)")
            st.plotly_chart(fig, use_container_width=True)

elif page == "Nutrition":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Nutrition — log meals (built-in DB)")
        food_input = st.text_input("Food / dish name (try: oatmeal, grilled chicken, salmon)")
        lookup = FOOD_DB.get(food_input.lower()) if food_input else None
        if lookup:
            st.info("Auto-filled nutrition from built-in food DB. You can edit values.")
        default_cal = lookup['cal'] if lookup else 300
        default_prot = lookup['protein'] if lookup else 15
        default_carbs = lookup['carbs'] if lookup else 30
        default_fat = lookup['fat'] if lookup else 10

        col1, col2, col3 = st.columns(3)
        with col1:
            calories = st.number_input("Calories (kcal)", value=float(default_cal))
        with col2:
            protein = st.number_input("Protein (g)", value=float(default_prot))
        with col3:
            carbs = st.number_input("Carbs (g)", value=float(default_carbs))
        fat = st.number_input("Fat (g)", value=float(default_fat))
        notes = st.text_area("Notes / tags (optional)")

        if st.button("Log meal"):
            insert_and_commit("INSERT INTO meals(email,meal_name,calories,protein,carbs,fat,notes,timestamp) VALUES(?,?,?,?,?,?,?,?)",
                              (email, food_input or "Custom meal", float(calories), float(protein), float(carbs), float(fat), notes, now_iso()))
            st.success("Meal logged")

        meals_df = query_df("SELECT timestamp, meal_name, calories, protein, carbs, fat FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
        if not meals_df.empty:
            meals_df['timestamp'] = pd.to_datetime(meals_df['timestamp'])
            st.subheader("Recent meal calories")
            fig = px.line(meals_df, x='timestamp', y='calories', title="Meal calories over time", markers=True)
            st.plotly_chart(fig, use_container_width=True)

elif page == "Exercises":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Exercises — log workouts")
        cat = st.selectbox("Category", list(EXERCISES.keys()))
        examples = EXERCISES[cat]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                st.markdown(f"**{ex['name']}**")
                st.write(ex['desc'])
        st.markdown("---")
        st.subheader("Log exercise")
        ex_name = st.text_input("Exercise name", value=examples[0]['name'])
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=600, value=20)
        est_cal = round(duration * 7)
        notes = st.text_area("Notes")
        if st.button("Log exercise"):
            insert_and_commit("INSERT INTO exercises(email,category,name,duration_min,calories_burned,notes,timestamp) VALUES(?,?,?,?,?,?,?)",
                              (email, cat, ex_name, int(duration), float(est_cal), notes, now_iso()))
            st.success(f"Logged {ex_name} ({duration} min)")

elif page == "Sleep & Habits":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Sleep & Habits")
        sl_date = st.date_input("Date", value=date.today())
        hours = st.number_input("Hours slept", min_value=0.0, max_value=24.0, value=7.5)
        if st.button("Log sleep"):
            insert_and_commit("INSERT INTO sleep_logs(email,date,hours) VALUES(?,?,?)", (email, sl_date.isoformat(), float(hours)))
            st.success("Sleep logged")
        st.markdown("### Habits")
        habit_name = st.text_input("Add habit (e.g., 'Drink water 8 cups')")
        if st.button("Add habit"):
            insert_and_commit("INSERT INTO habits(email,habit,last_completed,streak) VALUES(?,?,?,?)", (email, habit_name, None, 0))
            st.success("Habit added")

elif page == "Diet Generator":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Balanced Diet Generator & Meal Forecast")
        user = query_df("SELECT * FROM users WHERE email=?", (email,))
        def calc_target(user_row):
            try:
                w = float(user_row['weight_kg'])
                h = float(user_row['height_cm'])
                dob = user_row['dob']
                age = date.today().year - int(dob[:4]) if dob else 30
                sex = user_row['gender']
                s = 5 if str(sex).lower().startswith('m') else -161
                bmr = 10*w + 6.25*h - 5*age + s
                factor = {"sedentary":1.2, "light":1.375, "moderate":1.55, "active":1.725, "very active":1.9}.get(user_row.get('activity_level',''), 1.55)
                return int(bmr * factor)
            except Exception:
                return 2000
        target = calc_target(user.iloc[0]) if not user.empty else 2000
        st.metric("Estimated target daily calories", target)
        if st.button("Generate 7-day plan"):
            foods = list(FOOD_DB.keys())
            for d in range(7):
                breakfast = random.choice(foods)
                lunch = random.choice(foods)
                dinner = random.choice(foods)
                st.subheader((date.today() + timedelta(days=d)).isoformat())
                for m in [breakfast, lunch, dinner]:
                    info = FOOD_DB.get(m, {})
                    st.write(f"- {m} — ~{info.get('cal','--')} kcal, protein {info.get('protein','--')} g")

elif page == "Medical Advisor":
    st.header("Medical Advisor — home remedies & precautions (non-prescription)")
    st.markdown("*Disclaimer:* This is informational only, not a diagnosis. Seek professional care for severe symptoms.")
    sym = st.text_area("Describe symptoms")
    if st.button("Get advice") and sym.strip():
        s = sym.lower()
        adv = []
        if any(x in s for x in ["fever", "chills", "temperature"]):
            adv.append("Rest, fluids, paracetamol/ibuprofen as per instructions.")
        if any(x in s for x in ["cough", "sore throat", "throat", "congestion"]):
            adv.append("Warm saltwater gargles, warm fluids, honey for cough >1yr.")
        if not adv:
            adv.append("General: rest, hydrate, monitor. See physician if concerned.")
        st.write("\n\n".join(adv))

elif page == "AI Chatbot":
    st.header("AI Chatbot (offline canned Q&A)")
    q = st.text_input("Ask a question")
    if st.button("Ask"):
        if not q.strip():
            st.info("Type a question")
        else:
            ql = q.lower()
            answered = False
            for k, v in CANNED_QA.items():
                if k in ql:
                    st.markdown(f"*Q:* {q}\n\n*A:* {v}")
                    answered = True
                    break
            if not answered:
                st.markdown(f"*Q:* {q}\n\n*A:* I don't have a canned answer for that — try rephrasing.")

elif page == "Dashboard":
    if not st.session_state.logged_in:
        st.info("Please login first (sidebar).")
    else:
        st.header("Dashboard — Visual Summary")
        meals = query_df("SELECT timestamp, calories, protein, carbs, fat FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
        if not meals.empty:
            meals['timestamp'] = pd.to_datetime(meals['timestamp'])
            st.subheader("Calories over time")
            fig = px.line(meals, x='timestamp', y='calories', markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No meal data yet")

elif page == "Admin":
    if not st.session_state.logged_in:
        st.error("Admin access only. Login required.")
    elif not is_admin:
        st.error("Admin access only. Add your email to ADMIN_EMAILS in the script to enable.")
    else:
        st.header("Admin — view & export data")
        tabs = st.tabs(["Users", "Meals", "Water", "Exercises", "Sleep", "Habits", "Export"])
        with tabs[0]:
            df = query_df("SELECT * FROM users")
            st.dataframe(df)
        with tabs[1]:
            df = query_df("SELECT * FROM meals")
            st.dataframe(df)
        with tabs[2]:
            df = query_df("SELECT * FROM water_logs")
            st.dataframe(df)
        with tabs[3]:
            df = query_df("SELECT * FROM exercises")
            st.dataframe(df)
        with tabs[4]:
            df = query_df("SELECT * FROM sleep_logs")
            st.dataframe(df)
        with tabs[5]:
            df = query_df("SELECT * FROM habits")
            st.dataframe(df)
        with tabs[6]:
            st.subheader("Export CSVs")
            tables = [("users","SELECT * FROM users"), ("meals","SELECT * FROM meals"),
                      ("water","SELECT * FROM water_logs"), ("exercises","SELECT * FROM exercises")]
            for name, q in tables:
                df = query_df(q)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(f"Download {name}.csv", data=csv, file_name=f"{name}.csv")

# -------------------- OPTIONAL: dev-only reset button --------------------
if DEBUG:
    st.sidebar.markdown("---")
    if st.sidebar.button("DEV: Clear all auth codes"):
        cur.execute("DELETE FROM auth_codes")
        conn.commit()
        st.sidebar.success("Auth table cleared (dev).")
        debug_show_codes()




          
