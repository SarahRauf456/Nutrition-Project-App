
import streamlit as st
import sqlite3, os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import random, string
import plotly.express as px
import textwrap

st.set_page_config(page_title="Nutriion App BY SHARFIA — AI Health & Nutrition", layout="wide", initial_sidebar_state="expanded")


st.markdown("""
<style>
:root { --card-bg: rgba(255,255,255,0.92); }
html, body, .reportview-container, .main .block-container {
  background: linear-gradient(135deg, #FFEFBA 0%, #FFFFFF 50%, #D4A5FF 100%);
}
.block-container {
  border-radius: 12px;
  padding: 1.5rem;
}
.stAlert, .stSuccess, .stInfo, .stError {
  border-radius: 8px;
}
.card { background: var(--card-bg); border-radius: 12px; padding: 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.06); }
</style>
""", unsafe_allow_html=True)


DB_PATH = "data/nutriapp.db"
os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()


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

CREATE TABLE IF NOT EXISTS auth_codes (
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


def df_from_query(q, params=()):
    return pd.read_sql_query(q, conn, params=params)

def insert_and_commit(query, params=()):
    cur.execute(query, params)
    conn.commit()

def gen_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# -------------------- Small FOOD DB for auto nutrition lookup --------------------
# Values per typical serving (approx). You can expand this dictionary.
FOOD_DB = {
    "apple": {"cal": 95, "protein": 0.5, "carbs": 25, "fat": 0.3},
    "banana": {"cal": 105, "protein": 1.3, "carbs": 27, "fat": 0.4},
    "oatmeal": {"cal": 150, "protein": 5, "carbs": 27, "fat": 3},
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

# -------------------- Exercise info (images + short tips) --------------------
EXERCISES = {
    "Hands": [
        {"name":"Push-ups", "desc":"Bodyweight exercise for chest/triceps/shoulders.", "img":"https://images.unsplash.com/photo-1558611848-73f7eb4001d4?w=800&q=80"},
        {"name":"Bicep Curls", "desc":"Dumbbell curls for biceps (use light weight).", "img":"https://images.unsplash.com/photo-1605296867304-46d5465a13f1?w=800&q=80"}
    ],
    "Legs": [
        {"name":"Squats", "desc":"Great for quads/glutes. Keep knees aligned.", "img":"https://images.unsplash.com/photo-1546484959-f8d2f8d2b432?w=800&q=80"},
        {"name":"Lunges", "desc":"Walking or stationary lunges for legs & balance.", "img":"https://images.unsplash.com/photo-1594737625785-2e0b5d2bc9a5?w=800&q=80"}
    ],
    "Core": [
        {"name":"Plank", "desc":"Hold steady bodyline for core stability.", "img":"https://images.unsplash.com/photo-1558611847-6c3f1a5c9a5b?w=800&q=80"},
        {"name":"Russian Twist", "desc":"Rotational core exercise.", "img":"https://images.unsplash.com/photo-1534367614595-3f1a8d4a0e0a?w=800&q=80"}
    ],
    "Back": [
        {"name":"Superman", "desc":"Lying back-extension exercise.", "img":"https://images.unsplash.com/photo-1605296867304-46d5465a13f1?w=800&q=80"},
        {"name":"Bent-over Row", "desc":"With dumbbells or barbell for back strength.", "img":"https://images.unsplash.com/photo-1560250097-0b93528c311a?w=800&q=80"}
    ],
    "Full-body": [
        {"name":"Burpees", "desc":"High intensity full-body movement.", "img":"https://images.unsplash.com/photo-1554244934-336a2f2b6a24?w=800&q=80"},
        {"name":"Kettlebell Swing", "desc":"Hip hinge power movement (use appropriate weight).", "img":"https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&q=80"}
    ]
}

# -------------------- Offline AI Chatbot Q&A --------------------
CANNED_QA = {
    "how much protein": "Aim for ~1.2-2.0 g/kg body weight/day if you're active. Spread across meals.",
    "how many calories": "Calories depend on BMR and activity. Use profile (height/weight/age) to get recommended daily calories.",
    "what to eat for breakfast": "Try oats with fruit + a protein source (yogurt or egg) for balanced macros.",
    "how much water": "Aim for ~2000-3000 ml/day depending on activity, climate and body size. Track in Hydration tab.",
    "post workout meal": "A mix of protein + carbs helps recovery (e.g., chicken + rice or protein shake + banana).",
    "how to lose weight": "Create slight calorie deficit, prioritize protein, strength training, consistent sleep and hydration.",
    "how to gain muscle": "Progressive resistance training, adequate protein (~1.6-2.2 g/kg), and slight calorie surplus.",
    "best exercises for legs": "Squats, lunges, deadlifts (or hip hinge variations), and step-ups are effective.",
    "how to improve sleep": "Maintain consistent schedule, reduce screens before bed, keep room cool and dark.",
    "foods high in iron": "Spinach, lentils, red meat (if not vegetarian), and fortified cereals. Pair with Vitamin C.",
    "vitamin c sources": "Citrus, strawberries, bell peppers, broccoli.",
    "what is bmi": "BMI = weight(kg) / (height(m)^2). It's a rough indicator; not perfect for muscular people.",
    "healthy snacks": "Greek yogurt with fruit, nuts (small portions), veggie sticks with hummus.",
    "vegetarian protein": "Lentils, chickpeas, tofu, tempeh, Greek yogurt, cottage cheese.",
    "how to track macros": "Track calories and grams of protein/carbs/fats per meal — the app sums them over the day.",
    "how to reduce sugar": "Gradually reduce sugary drinks, choose whole fruit instead of juice, read labels.",
    "what is a balanced plate": "Half vegetables, quarter lean protein, quarter whole grains/starches, healthy fats in moderation.",
    "keto basics": "High fat, very low carb; not suitable for everyone. Consult a clinician for medical conditions.",
    "intermittent fasting": "Time-restricted eating can work for some; focus on overall calorie & nutrient quality.",
    "hydration tips": "Carry a bottle, set timed reminders, drink with meals, include electrolytes when sweating a lot.",
    "posture tips": "Strengthen core, stretch chest/hip flexors, check ergonomic setup at work.",
    "when to see a doctor": "Seek care for severe pain, shortness of breath, chest pain, sudden weakness, high fever."
}
# Expand answers count ~22; user requested 20-30 — we have 22 above.

# -------------------- Sidebar: login & admin --------------------
st.sidebar.title("Account & Controls")

if "email" not in st.session_state:
    # lightweight magic-code login for demo
    st.sidebar.subheader("Sign in (demo)")
    email_in = st.sidebar.text_input("Email (demo)", value="")
    if st.sidebar.button("Send code"):
        if email_in:
            code = gen_code()
            insert_and_commit("INSERT INTO auth_codes(email,code,created_at) VALUES(?,?,?)", (email_in, code, datetime.utcnow().isoformat()))
            # For demo: show code in UI (in production you'd email it)
            st.sidebar.success("Demo code generated — check below")
            st.sidebar.info(f"Your demo code is: {code}")
            st.session_state["_pending_email"] = email_in
    code_in = st.sidebar.text_input("Enter code")
    if st.sidebar.button("Verify code"):
        if "_pending_email" in st.session_state and code_in:
            q = "SELECT code FROM auth_codes WHERE email=? ORDER BY created_at DESC LIMIT 1"
            res = cur.execute(q, (st.session_state["_pending_email"],)).fetchone()
            if res and res[0] == code_in:
                st.session_state["email"] = st.session_state["_pending_email"]
                st.sidebar.success("Logged in (demo)")
                # ensure user exists
                user = cur.execute("SELECT email FROM users WHERE email=?", (st.session_state["email"],)).fetchone()
                if not user:
                    insert_and_commit("INSERT INTO users(email, name, created_at) VALUES(?,?,?)", (st.session_state["email"], st.session_state["email"].split('@')[0], datetime.utcnow().isoformat()))
                st.experimental_rerun()
            else:
                st.sidebar.error("Invalid code")
    st.stop()
else:
    email = st.session_state["email"]
    st.sidebar.markdown(f"{email}")
    if st.sidebar.button("Logout"):
        del st.session_state["email"]
        st.experimental_rerun()

# Admin mode (detect admin emails quickly)
ADMIN_EMAILS = ["admin@example.com"]
is_admin = email in ADMIN_EMAILS

# Navigation
page = st.sidebar.selectbox("Open", [
    "Dashboard", "Profile (Manage)", "Hydration", "Nutrition", "Exercises",
    "Sleep & Habits", "Diet Generator", "Medical Advisor", "AI Chatbot",
    "Admin"
])

# -------------------- PROFILE PAGE --------------------
if page == "Profile (Manage)":
    st.header("Profile — manage your info")
    user = df_from_query("SELECT * FROM users WHERE email=?", (email,))
    if user.empty:
        # show edit form
        st.info("No profile — create one")
    row = user.iloc[0] if not user.empty else {}
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", value=row.get("name",""))
        dob = st.date_input("Date of birth", value=datetime.strptime(row.get("dob","1990-01-01"), "%Y-%m-%d").date() if row.get("dob") else date(1990,1,1))
        gender = st.selectbox("Gender", options=["male","female","other"], index=0 if row.get("gender","male").lower().startswith("m") else 1)
    with col2:
        height_cm = st.number_input("Height (cm)", value=float(row.get("height_cm") or 170.0))
        weight_kg = st.number_input("Weight (kg)", value=float(row.get("weight_kg") or 70.0))
        activity = st.selectbox("Activity level", ["sedentary","light","moderate","active","very active"], index=2)
        goals = st.text_input("Goals", value=row.get("goals","maintain"))
    if st.button("Save Profile"):
        insert_and_commit("""INSERT OR REPLACE INTO users(email,name,dob,height_cm,weight_kg,gender,activity_level,goals,created_at)
                           VALUES(?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM users WHERE email=?),?))""",
                          (email, name, dob.isoformat(), height_cm, weight_kg, gender, activity, goals, email, datetime.utcnow().isoformat()))
        st.success("Profile saved")

# -------------------- HYDRATION PAGE --------------------
elif page == "Hydration":
    st.header("Hydration tracker")
    ml = st.number_input("Add water (ml)", min_value=50, max_value=5000, value=250, step=50)
    if st.button("Log water"):
        insert_and_commit("INSERT INTO water_logs(email,ml,timestamp) VALUES(?,?,?)", (email, int(ml), datetime.utcnow().isoformat()))
        st.success(f"Logged {ml} ml")

    df = df_from_query("SELECT * FROM water_logs WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        daily = df.groupby(df['timestamp'].dt.date)['ml'].sum().reset_index()
        daily.columns = ['date','ml']
        fig = px.bar(daily, x='date', y='ml', title="Daily Water Intake (ml)", labels={"ml":"ml"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No water logs yet")

# -------------------- NUTRITION PAGE --------------------
elif page == "Nutrition":
    st.header("Nutrition / Meal tracker")
    # allow quick food name entry with lookup
    food_name = st.text_input("Food / Dish name (try 'oatmeal', 'grilled chicken', 'salmon')")
    auto_lookup = FOOD_DB.get(food_name.lower())
    col1, col2, col3 = st.columns(3)
    if auto_lookup:
        default_cal = auto_lookup['cal']
        default_prot = auto_lookup['protein']
        default_carbs = auto_lookup['carbs']
        default_fat = auto_lookup['fat']
        st.info("Auto-filled nutrition from built-in food DB (you can edit).")
    else:
        default_cal = 300
        default_prot = 15
        default_carbs = 35
        default_fat = 10

    with col1:
        calories = st.number_input("Calories (kcal)", value=float(default_cal))
    with col2:
        protein = st.number_input("Protein (g)", value=float(default_prot))
    with col3:
        carbs = st.number_input("Carbs (g)", value=float(default_carbs))
    fat = st.number_input("Fat (g)", value=float(default_fat))
    notes = st.text_area("Notes / Tags (optional)")

    if st.button("Log meal"):
        insert_and_commit("INSERT INTO meals(email,meal_name,calories,protein,carbs,fat,notes,timestamp) VALUES(?,?,?,?,?,?,?,?)",
                          (email, food_name or "Custom meal", float(calories), float(protein), float(carbs), float(fat), notes, datetime.utcnow().isoformat()))
        st.success("Meal logged")

    df = df_from_query("SELECT * FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.subheader("Calories over time")
        fig = px.line(df, x='timestamp', y='calories', title="Meal Calories Over Time")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Macro split (last 30 entries)")
        last = df.head(30)
        total_prot = last['protein'].sum() * 4
        total_carbs = last['carbs'].sum() * 4
        total_fat = last['fat'].sum() * 9
        macro_df = pd.DataFrame({
            "macro":["protein","carbs","fat"],
            "kcal":[total_prot, total_carbs, total_fat]
        })
        fig2 = px.pie(macro_df, names='macro', values='kcal', title="Macro calories (estimated)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No meals logged yet")

# -------------------- EXERCISES PAGE --------------------
elif page == "Exercises":
    st.header("Exercise Tracker & Info")
    cat = st.selectbox("Category", options=list(EXERCISES.keys()))
    # show sample exercises with images and short texts
    st.markdown("### Examples")
    cols = st.columns(2)
    sample_list = EXERCISES[cat]
    for i, exinfo in enumerate(sample_list):
        c = cols[i % 2]
        with c:
            st.image(exinfo['img'], width=260)
            st.markdown(f"{exinfo['name']}")
            st.write(exinfo['desc'])

    st.markdown("---")
    st.subheader("Log your exercise")
    ex_name = st.text_input("Exercise name (or choose above)", value=sample_list[0]['name'])
    duration = st.number_input("Duration (min)", value=20, min_value=1)
    est_cal = int(duration * 7)  # simple estimate 7 kcal/min
    notes = st.text_area("Notes (optional)")

    if st.button("Log exercise"):
        # IMPORTANT: match table columns — include timestamp
        insert_and_commit("INSERT INTO exercises(email,category,name,duration_min,calories_burned,notes,timestamp) VALUES(?,?,?,?,?,?,?)",
                          (email, cat, ex_name, int(duration), float(est_cal), notes, datetime.utcnow().isoformat()))
        st.success(f"Logged {ex_name} ({duration} min, est {est_cal} kcal)")

    # show exercise breakdown pie chart
    exdf = df_from_query("SELECT category, COUNT(*) as cnt FROM exercises WHERE email=? GROUP BY category", (email,))
    if not exdf.empty:
        fig = px.pie(exdf, names='category', values='cnt', title="Exercise categories distribution")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No exercises logged yet")

# -------------------- SLEEP & HABITS --------------------
elif page == "Sleep & Habits":
    st.header("Sleep tracker & Habits")
    sl_date = st.date_input("Date", value=date.today())
    hours = st.number_input("Hours slept", value=7.5, min_value=0.0, max_value=24.0)
    if st.button("Log sleep"):
        insert_and_commit("INSERT INTO sleep_logs(email,date,hours) VALUES(?,?,?)", (email, sl_date.isoformat(), float(hours)))
        st.success("Sleep logged")

    st.markdown("### Habits")
    habit_name = st.text_input("New habit (e.g., 'Drink water 8 cups')")
    if st.button("Add habit"):
        insert_and_commit("INSERT INTO habits(email,habit,last_completed,streak) VALUES(?,?,?,?)", (email, habit_name, None, 0))
        st.success("Habit added")

    # list habits
    hdf = df_from_query("SELECT id,habit,last_completed,streak FROM habits WHERE email=?", (email,))
    if not hdf.empty:
        for _, r in hdf.iterrows():
            col1, col2 = st.columns([4,1])
            with col1:
                st.write(f"{r['habit']}** — streak: {r['streak']}")
                st.write(f"last: {r['last_completed']}")
            with col2:
                if st.button(f"Complete_{int(r['id'])}"):
                    last = r['last_completed']
                    today = date.today().isoformat()
                    if last:
                        lastd = date.fromisoformat(last)
                        if (date.today() - lastd).days == 1:
                            new_streak = int(r['streak']) + 1
                        elif (date.today() - lastd).days == 0:
                            new_streak = int(r['streak'])
                        else:
                            new_streak = 1
                    else:
                        new_streak = 1
                    insert_and_commit("UPDATE habits SET last_completed=?, streak=? WHERE id=?", (today, new_streak, int(r['id'])))
                    st.experimental_rerun()
    else:
        st.info("No habits yet")

# -------------------- DIET GENERATOR --------------------
elif page == "Diet Generator":
    st.header("Balanced Diet Generator")
    user = df_from_query("SELECT * FROM users WHERE email=?", (email,))
    # simple calorie target using Mifflin-St Jeor
    def recommended_calories(row):
        try:
            weight = float(row['weight_kg'])
            height = float(row['height_cm'])
            age = (date.today().year - int(row['dob'][:4])) if row['dob'] else 30
            sex = row['gender']
            s = 5 if str(sex).lower().startswith('m') else -161
            bmr = 10*weight + 6.25*height - 5*age + s
            factor = 1.55
            return int(bmr * factor)
        except:
            return 2000
    target = recommended_calories(user.iloc[0]) if not user.empty else 2000
    st.metric("Target calories (est)", target)

    if st.button("Generate 7-day balanced plan"):
        # naive generator: reuse FOOD_DB entries
        keys = list(FOOD_DB.keys())
        plan = []
        for d in range(7):
            breakfast = random.choice(keys)
            lunch = random.choice(keys)
            dinner = random.choice(keys)
            plan.append({"day": (date.today() + timedelta(days=d)).isoformat(), "meals":[breakfast,lunch,dinner]})
        for p in plan:
            st.subheader(p['day'])
            for m in p['meals']:
                info = FOOD_DB.get(m, {})
                st.write(f"- {m} — approx {info.get('cal','--')} kcal, protein {info.get('protein','--')} g")

# -------------------- MEDICAL ADVISOR --------------------
elif page == "Medical Advisor":
    st.header("Medical Advisor — home remedies & precautions (non-prescription)")
    st.markdown("*Disclaimer:* This is general information only and not a diagnosis. Seek medical help for severe/red flag symptoms.")
    symptoms = st.text_area("Describe symptoms (e.g., 'sore throat and fever')")
    if st.button("Get advice"):
        # simple rule-based advice (no meds)
        text = []
        s = symptoms.lower()
        if any(x in s for x in ["fever","chills","temperature"]):
            text.append("Possible: viral infection. Remedies: rest, fluids, paracetamol/ibuprofen as per instructions. Seek care if >39°C or lasting >48h.")
        if any(x in s for x in ["cough","sore throat","throat","congestion"]):
            text.append("Saltwater gargles, warm drinks, humidifier. See doctor if breathing difficulty.")
        if any(x in s for x in ["stomach","nausea","vomit","diarrhea"]):
            text.append("Hydrate with ORS, BRAT diet short term. See care for severe pain/blood in stool.")
        if any(x in s for x in ["back","neck","pain"]):
            text.append("Gentle movement, heat/ice, avoid heavy lifting. See physio if numbness/weakness.")
        if not text:
            text.append("General: rest, hydrate, balanced diet, monitor symptoms. Contact PCP if unsure.")
        text.append("Red flags: chest pain, severe breathing difficulty, fainting, sudden weakness, severe dehydration — seek emergency care.")
        st.write("\n\n".join(text))

# -------------------- AI CHATBOT (offline canned) --------------------
elif page == "AI Chatbot":
    st.header("Offline AI Chatbot (no API) — quick Q&A")
    q = st.text_input("Ask a question (try: 'how much protein', 'post workout meal', 'how to improve sleep')")
    if st.button("Ask"):
        if not q.strip():
            st.info("Type a question")
        else:
            got = False
            qlow = q.lower()
            # simple substring matching across canned QA
            for k,v in CANNED_QA.items():
                if k in qlow or any(word in qlow for word in k.split()):
                    st.markdown(f"*Q:* {q}\n\n*A:* {v}")
                    got = True
                    break
            if not got:
                # fallback: search keywords
                for k,v in CANNED_QA.items():
                    if any(tok in qlow for tok in k.split()):
                        st.markdown(f"*Q:* {q}\n\n*A:* {v}")
                        got = True
                        break
            if not got:
                st.markdown(f"*Q:* {q}\n\n*A:* I'm not sure — try rephrasing. Common topics: protein, calories, hydration, sleep, workouts.")

# -------------------- DASHBOARD --------------------
elif page == "Dashboard":
    st.header("Dashboard — Visuals & Summary")
    # Meals calories chart
    mdf = df_from_query("SELECT timestamp, calories, protein, carbs, fat FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not mdf.empty:
        mdf['timestamp'] = pd.to_datetime(mdf['timestamp'])
        st.subheader("Calories (recent meals)")
        fig = px.scatter(mdf, x='timestamp', y='calories', hover_data=['protein','carbs','fat'])
        fig.update_layout(margin=dict(t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)
        # macro pie (last 30)
        last = mdf.head(30)
        prot_k = float(last['protein'].sum())*4
        carb_k = float(last['carbs'].sum())*4
        fat_k = float(last['fat'].sum())*9
        mac_df = pd.DataFrame({'macro':['Protein','Carbs','Fats'], 'kcal':[prot_k, carb_k, fat_k]})
        st.subheader("Macro split (last 30 meals)")
        fig2 = px.pie(mac_df, names='macro', values='kcal', title='Macro calories (approx)')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No meals to show in dashboard")

    # Exercise breakdown
    exdf = df_from_query("SELECT category, COUNT(*) as cnt FROM exercises WHERE email=? GROUP BY category", (email,))
    if not exdf.empty:
        st.subheader("Exercise categories")
        fig3 = px.pie(exdf, names='category', values='cnt', title="Exercise category distribution")
        st.plotly_chart(fig3, use_container_width=True)

    # Water daily
    wdf = df_from_query("SELECT timestamp, ml FROM water_logs WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not wdf.empty:
        wdf['timestamp'] = pd.to_datetime(wdf['timestamp'])
        daily = wdf.groupby(wdf['timestamp'].dt.date)['ml'].sum().reset_index()
        daily.columns = ['date','ml']
        st.subheader("Daily water intake")
        fig4 = px.bar(daily, x='date', y='ml', title="Daily water (ml)")
        st.plotly_chart(fig4, use_container_width=True)

    
    sdf = df_from_query("SELECT date, hours FROM sleep_logs WHERE email=? ORDER BY date DESC LIMIT 365", (email,))
    if not sdf.empty:
        sdf['date'] = pd.to_datetime(sdf['date'])
        st.subheader("Sleep (hours)")
        fig5 = px.line(sdf, x='date', y='hours', title="Sleep hours over time")
        st.plotly_chart(fig5, use_container_width=True)

elif page == "Admin":
    if not is_admin:
        st.error("Admin access only. To enable, add your email to ADMIN_EMAILS in the script.")
    else:
        st.header("Admin — View stored data & export")
        tabs = st.tabs(["Users","Meals","Water","Exercises","Sleep","Habits","Export"])
        with tabs[0]:
            df = df_from_query("SELECT * FROM users")
            st.dataframe(df)
        with tabs[1]:
            df = df_from_query("SELECT * FROM meals")
            st.dataframe(df)
        with tabs[2]:
            df = df_from_query("SELECT * FROM water_logs")
            st.dataframe(df)
        with tabs[3]:
            df = df_from_query("SELECT * FROM exercises")
            st.dataframe(df)
        with tabs[4]:
            df = df_from_query("SELECT * FROM sleep_logs")
            st.dataframe(df)
        with tabs[5]:
            df = df_from_query("SELECT * FROM habits")
            st.dataframe(df)
        with tabs[6]:
            st.subheader("Export CSVs")
            for name, q in [("users","SELECT * FROM users"), ("meals","SELECT * FROM meals"),
                            ("water","SELECT * FROM water_logs"), ("exercises","SELECT * FROM exercises")]:
                df = df_from_query(q)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(f"Download {name}.csv", data=csv, file_name=f"{name}.csv")
