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

APP_TITLE = "Nutrion App BY SHARFIA— AI Health & Nutrition Analyzer"
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "nutriapp.db")
ADMIN_EMAILS = [""]  
MAGIC_CODE_TTL_MIN = 15

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")

# -------------------- THEME B CSS (Blue / Green Fresh) --------------------
st.markdown(
    """
    <style>
    /* page background gradient */
    .reportview-container, .main .block-container{
        background: linear-gradient(135deg, #e6fffa 0%, #e0f2fe 40%, #dafaf3 100%);
        border-radius: 12px;
        padding: 1.2rem;
    }
    /* card look */
    .card {
        background: rgba(255,255,255,0.95);
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 6px 20px rgba(17, 94, 89, 0.08);
    }
    /* accent headings */
    h1, h2, h3 { color: #0f766e; }
    /* sidebar headers */
    .stSidebar .css-1d391kg { background: linear-gradient(180deg,#ffffff 0%, #f0f9f8 100%); }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- DB INIT --------------------
os.makedirs(DB_DIR, exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Create tables with consistent column names
cur.executescript(
    """
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
"""
)
conn.commit()

# -------------------- UTILITIES --------------------
def insert_and_commit(query, params=()):
    cur.execute(query, params)
    conn.commit()

def query_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

def gen_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def now_iso():
    return datetime.utcnow().isoformat()

# -------------------- SMALL FOOD DB (auto nutrition lookup) --------------------
# Expandable: values approx per serving
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

# -------------------- EXERCISE METADATA (real image URLs) --------------------
EXERCISES = {
    "Hands": [
        {"name": "Push-ups", "desc": "Bodyweight exercise for chest/triceps/shoulders.", "img": "https://images.unsplash.com/photo-1558611848-73f7eb4001d4?w=800&q=80"},
        {"name": "Bicep Curls", "desc": "Dumbbell curls for biceps.", "img": "https://images.unsplash.com/photo-1605296867304-46d5465a13f1?w=800&q=80"},
    ],
    "Legs": [
        {"name": "Squats", "desc": "Quad & glute-builder. Keep knees aligned.", "img": "https://images.unsplash.com/photo-1546484959-f8d2f8d2b432?w=800&q=80"},
        {"name": "Lunges", "desc": "Balance & unilateral strength.", "img": "https://images.unsplash.com/photo-1594737625785-2e0b5d2bc9a5?w=800&q=80"},
    ],
    "Core": [
        {"name": "Plank", "desc": "Hold straight bodyline for core stability.", "img": "https://images.unsplash.com/photo-1558611847-6c3f1a5c9a5b?w=800&q=80"},
        {"name": "Russian Twist", "desc": "Rotational core exercise.", "img": "https://images.unsplash.com/photo-1534367614595-3f1a8d4a0e0a?w=800&q=80"},
    ],
    "Back": [
        {"name": "Superman", "desc": "Back-extension to target lower back.", "img": "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=800&q=80"},
        {"name": "Bent-over Row", "desc": "Rowing motion to strengthen back.", "img": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&q=80"},
    ],
    "Full-body": [
        {"name": "Burpees", "desc": "High-intensity full-body movement.", "img": "https://images.unsplash.com/photo-1554244934-336a2f2b6a24?w=800&q=80"},
        {"name": "Kettlebell Swing", "desc": "Hip hinge power movement.", "img": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&q=80"},
    ],
}

# -------------------- CANNED QA (offline chatbot) --------------------
CANNED_QA = {
    "how much protein": "Aim for ~1.2-2.0 g/kg of body weight per day if active. Spread it across meals.",
    "how many calories": "Calories depend on BMR and activity. Use Profile to estimate—balance energy in vs out.",
    "what to eat for breakfast": "Oats with fruit + protein (yogurt or egg) is a balanced start.",
    "how much water": "Aim ~2000–3000 ml/day, more if active or hot. Log water in Hydration tab.",
    "post workout meal": "Combining protein + carbs helps recovery (e.g., chicken + rice or protein shake + banana).",
    "how to lose weight": "Mild calorie deficit, prioritize protein & strength training, sleep, hydration, and consistency.",
    "how to gain muscle": "Progressive overload resistance training + 1.6–2.2 g/kg protein and slight calorie surplus.",
    "best exercises for legs": "Squats, lunges, deadlifts, step-ups. Focus on form and progressive loading.",
    "how to improve sleep": "Keep consistent schedule, reduce screens 1 hour before bed, cool/dark room, avoid heavy late meals.",
    "foods high in iron": "Spinach, lentils, beef, fortified cereals. Pair with vitamin C to increase absorption.",
    "vitamin c sources": "Citrus, strawberries, bell peppers, broccoli.",
    "what is bmi": "BMI = weight(kg) / (height(m)^2). Useful rough indicator but imperfect for muscular builds.",
    "healthy snacks": "Greek yogurt with fruit, nuts (small portion), veggies with hummus.",
    "vegetarian protein": "Lentils, chickpeas, tofu, tempeh, Greek yogurt, cottage cheese.",
    "how to track macros": "Log grams of protein/carbs/fats per meal—the app sums daily totals in Dashboard.",
    "how to reduce sugar": "Swap sugary drinks for water, choose whole fruits, read labels and reduce added sugar gradually.",
    "what is a balanced plate": "Half vegetables, quarter lean protein, quarter whole grains/starch, small healthy fats.",
    "keto basics": "High fat, very low carb. Not suitable for everyone; consult with clinician if chronic conditions exist.",
    "intermittent fasting": "Time-restricted eating can help some—focus on overall calories & nutrients during eating window.",
    "hydration tips": "Carry a bottle, sip throughout day, drink with meals, use small goals to build habit.",
    "posture tips": "Strengthen core, stretch chest & hip flexors, set ergonomic workspace; take breaks to move.",
    "when to see a doctor": "Seek care for chest pain, difficulty breathing, sudden weakness, severe dehydration, or severe/unusual symptoms."
}



# -------------------- NAVIGATION --------------------
st.sidebar.markdown("---")
page = st.sidebar.selectbox("Open", [
    "Dashboard", "Profile", "Hydration", "Nutrition", "Exercises",
    "Sleep & Habits", "Diet Generator", "Medical Advisor", "AI Chatbot", "Admin"
])

# -------------------- PROFILE --------------------
if page == "Profile":
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
        insert_and_commit("""INSERT OR REPLACE INTO users(email,name,dob,height_cm,weight_kg,gender,activity_level,goals,created_at)
            VALUES(?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM users WHERE email=?),?))""",
            (email, name, dob.isoformat(), height_cm, weight_kg, gender, activity, goals, email, now_iso()))
        st.success("Profile saved")

# -------------------- HYDRATION --------------------
elif page == "Hydration":
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
        fig = px.bar(daily, x='date', y='ml', title="Daily water (ml)", color='ml', color_continuous_scale=px.colors.sequential.Teal)
        st.plotly_chart(fig, use_container_width=True)

# -------------------- NUTRITION --------------------
elif page == "Nutrition":
    st.header("Nutrition — log meals (auto nutrition from built-in DB)")
    food_input = st.text_input("Food / dish name (try: oatmeal, grilled chicken, salmon)")
    lookup = FOOD_DB.get(food_input.lower())
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

    # recent meals + charts
    meals_df = query_df("SELECT timestamp, meal_name, calories, protein, carbs, fat FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not meals_df.empty:
        meals_df['timestamp'] = pd.to_datetime(meals_df['timestamp'])
        st.subheader("Recent meal calories")
        fig = px.line(meals_df, x='timestamp', y='calories', title="Meal calories over time", markers=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Macro split (approx — last 30 entries)")
        last30 = meals_df.head(30)
        prot_kcal = last30['protein'].sum() * 4
        carb_kcal = last30['carbs'].sum() * 4
        fat_kcal = last30['fat'].sum() * 9
        macro_df = pd.DataFrame({"macro": ["Protein", "Carbs", "Fat"], "kcal": [prot_kcal, carb_kcal, fat_kcal]})
        fig2 = px.pie(macro_df, names='macro', values='kcal', color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No meals logged yet")

# -------------------- EXERCISES --------------------
elif page == "Exercises":
    st.header("Exercises — log workouts & see examples")
    cat = st.selectbox("Category", list(EXERCISES.keys()))
    st.markdown("#### Examples")
    examples = EXERCISES[cat]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        with cols[i % 2]:
            st.image(ex['img'], width=260)
            st.markdown(f"{ex['name']}")
            st.write(ex['desc'])

    st.markdown("---")
    st.subheader("Log exercise")
    ex_name = st.text_input("Exercise name", value=examples[0]['name'])
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=600, value=20)
    est_cal = round(duration * 7)  # simple universal estimate (kcal/min)
    notes = st.text_area("Notes")
    if st.button("Log exercise"):
        insert_and_commit("INSERT INTO exercises(email,category,name,duration_min,calories_burned,notes,timestamp) VALUES(?,?,?,?,?,?,?)",
                          (email, cat, ex_name, int(duration), float(est_cal), notes, now_iso()))
        st.success(f"Logged {ex_name} ({duration} min, est {est_cal} kcal)")

    ex_df = query_df("SELECT timestamp, category, name, duration_min, calories_burned FROM exercises WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not ex_df.empty:
        ex_df['timestamp'] = pd.to_datetime(ex_df['timestamp'])
        st.subheader("Calories burned over time")
        fig = px.bar(ex_df, x='timestamp', y='calories_burned', color='category', title="Exercise: calories burned")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No exercise logs yet")

# -------------------- SLEEP & HABITS --------------------
elif page == "Sleep & Habits":
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

    hdf = query_df("SELECT id, habit, last_completed, streak FROM habits WHERE email=?", (email,))
    if not hdf.empty:
        for _, r in hdf.iterrows():
            cols = st.columns([4,1])
            with cols[0]:
                st.write(f"{r['habit']}** — Streak: {r['streak']}")
                st.write(f"Last: {r['last_completed']}")
            with cols[1]:
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

# -------------------- DIET GENERATOR & FORECAST --------------------
elif page == "Diet Generator":
    st.header("Balanced Diet Generator & Meal Forecast")
    # get simple calorie target from profile (Mifflin-St Jeor)
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
            factor = {"sedentary":1.2, "light":1.375, "moderate":1.55, "active":1.725, "very active":1.9}.get(user_row['activity_level'], 1.55)
            return int(bmr * factor)
        except Exception:
            return 2000
    target = calc_target(user.iloc[0]) if not user.empty else 2000
    st.metric("Estimated target daily calories", target)

    if st.button("Generate 7-day plan"):
        foods = list(FOOD_DB.keys())
        plan = []
        for d in range(7):
            breakfast = random.choice(foods)
            lunch = random.choice(foods)
            dinner = random.choice(foods)
            plan.append((date.today() + timedelta(days=d)).isoformat(), [breakfast, lunch, dinner])
        for d, meals in plan:
            st.subheader(d)
            for m in meals:
                info = FOOD_DB.get(m, {})
                st.write(f"- {m} — ~{info.get('cal','--')} kcal, protein {info.get('protein','--')} g")

    st.markdown("---")
    st.subheader("Simple meal forecast (based on recent average calories)")
    days = st.slider("Forecast days", 1, 7, 3)
    recent = query_df("SELECT calories, timestamp FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 50", (email,))
    if recent.empty:
        st.info("Not enough meal data — log meals first")
    else:
        recent['timestamp'] = pd.to_datetime(recent['timestamp'])
        mean = recent['calories'].mean()
        # pick nearest foods as forecast
        foods = list(FOOD_DB.items())
        forecast = []
        for i in range(days):
            diffs = [(abs(v['cal'] - mean), k, v) for k, v in foods]
            diffs.sort()
            forecast.append(diffs[0][1])
        for i, f in enumerate(forecast):
            st.write(f"Day {i+1}: {f} — approx {FOOD_DB[f]['cal']} kcal")

# -------------------- MEDICAL ADVISOR --------------------
elif page == "Medical Advisor":
    st.header("Medical Advisor — home remedies & precautions (non-prescription)")
    st.markdown("*Disclaimer:* This is informational only, not a diagnosis. Seek professional care for severe symptoms.")
    sym = st.text_area("Describe symptoms (e.g., 'sore throat and fever')")
    if st.button("Get advice") and sym.strip():
        s = sym.lower()
        adv = []
        if any(x in s for x in ["fever", "chills", "temperature"]):
            adv.append("Possible mild infection/viral illness. Rest, fluids, paracetamol/ibuprofen per instructions. Seek care if high fever or worsening.")
        if any(x in s for x in ["cough", "sore throat", "throat", "congestion"]):
            adv.append("Warm saltwater gargles, warm fluids, honey for cough >1yr, humidifier.")
        if any(x in s for x in ["stomach", "nausea", "vomit", "diarrhea"]):
            adv.append("Hydration (ORS), BRAT diet short-term. See care if severe pain or blood in stool.")
        if any(x in s for x in ["back", "neck", "pain"]):
            adv.append("Gentle movement, heat/cold packs, avoid heavy lifting. See physio if numbness/weakness.")
        if not adv:
            adv.append("General: rest, hydrate, balanced meals, monitor. Contact PCP if concerned.")
        adv.append("Red flags: chest pain, severe breathing difficulty, sudden weakness, fainting, signs of severe dehydration — seek urgent care.")
        st.write("\n\n".join(adv))

# -------------------- AI CHATBOT (offline canned) --------------------
elif page == "AI Chatbot":
    st.header("AI Chatbot (offline canned Q&A)")
    query = st.text_input("Ask a question (examples: 'how much protein', 'post workout meal')")
    if st.button("Ask"):
        if not query.strip():
            st.info("Type a question")
        else:
            ql = query.lower()
            answered = False
            # try direct key match
            for k, v in CANNED_QA.items():
                if k in ql:
                    st.markdown(f"*Q:* {query}\n\n*A:* {v}")
                    answered = True
                    break
            # fallback: substring match on any keyword in keys
            if not answered:
                for k, v in CANNED_QA.items():
                    for token in k.split():
                        if token in ql:
                            st.markdown(f"*Q:* {query}\n\n*A:* {v}")
                            answered = True
                            break
                    if answered:
                        break
            if not answered:
                st.markdown(f"*Q:* {query}\n\n*A:* I don't have a canned answer for that — try rephrasing (topics: protein, calories, water, sleep, workouts).")

# -------------------- DASHBOARD --------------------
elif page == "Dashboard":
    st.header("Dashboard — Visual Summary")
    # Meals
    meals = query_df("SELECT timestamp, calories, protein, carbs, fat FROM meals WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not meals.empty:
        meals['timestamp'] = pd.to_datetime(meals['timestamp'])
        st.subheader("Calories over time")
        fig = px.line(meals, x='timestamp', y='calories', title="Calories (meals)", markers=True)
        fig.update_traces(line=dict(color="#0f766e"))
        st.plotly_chart(fig, use_container_width=True)

        # macro pie last 30
        last30 = meals.head(30)
        prot_k = last30['protein'].sum() * 4
        carb_k = last30['carbs'].sum() * 4
        fat_k = last30['fat'].sum() * 9
        macro_df = pd.DataFrame({"macro": ["Protein", "Carbs", "Fat"], "kcal": [prot_k, carb_k, fat_k]})
        st.subheader("Macro split (last 30 meals)")
        fig2 = px.pie(macro_df, names='macro', values='kcal', color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No meal data yet — log meals to populate dashboard")

    # Exercises
    ex = query_df("SELECT category, COUNT(*) as cnt FROM exercises WHERE email=? GROUP BY category", (email,))
    if not ex.empty:
        st.subheader("Exercise categories (distribution)")
        fig3 = px.pie(ex, names='category', values='cnt', color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(fig3, use_container_width=True)

    # Water
    w = query_df("SELECT timestamp, ml FROM water_logs WHERE email=? ORDER BY timestamp DESC LIMIT 365", (email,))
    if not w.empty:
        w['timestamp'] = pd.to_datetime(w['timestamp'])
        daily = w.groupby(w['timestamp'].dt.date)['ml'].sum().reset_index()
        daily.columns = ['date', 'ml']
        st.subheader("Daily water intake")
        fig4 = px.bar(daily, x='date', y='ml', color='ml', color_continuous_scale=px.colors.sequential.Teal)
        st.plotly_chart(fig4, use_container_width=True)

    # Sleep
    s = query_df("SELECT date, hours FROM sleep_logs WHERE email=? ORDER BY date DESC LIMIT 365", (email,))
    if not s.empty:
        s['date'] = pd.to_datetime(s['date'])
        st.subheader("Sleep (hours)")
        fig5 = px.line(s, x='date', y='hours', title="Sleep hours", markers=True)
        st.plotly_chart(fig5, use_container_width=True)

    # Simple recommendations
    st.subheader("Smart recommendations")
    recs = []
    # hydration in last 24h
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    tw = cur.execute("SELECT SUM(ml) FROM water_logs WHERE email=? AND timestamp>=?", (email, since)).fetchone()[0]
    tw = int(tw) if tw else 0
    if tw < 1800:
        recs.append(f"You logged {tw} ml in the last 24h — aim for ~2000-3000 ml/day.")
    # exercise check last 7 days
    cnt_ex = cur.execute("SELECT COUNT(*) FROM exercises WHERE email=? AND timestamp>=?", (email, (datetime.utcnow() - timedelta(days=7)).isoformat())).fetchone()[0]
    if cnt_ex < 2:
        recs.append("You logged fewer than 2 exercise sessions in the last 7 days — try a short routine this week.")
    # sleep avg 7 days
    avg_sleep = query_df("SELECT AVG(hours) as avg_hours FROM sleep_logs WHERE email=? AND date>=?", (email, (date.today() - timedelta(days=7)).isoformat()))
    if not avg_sleep.empty and avg_sleep['avg_hours'].iloc[0] and avg_sleep['avg_hours'].iloc[0] < 7:
        recs.append(f"Average sleep last 7 days: {round(avg_sleep['avg_hours'].iloc[0],1)} hrs — target 7-9 hrs.")
    if recs:
        for r in recs:
            st.info(r)
    else:
        st.success("You're doing well — keep it up!")

# -------------------- ADMIN --------------------
elif page == "Admin":
    if not is_admin:
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

# -------------------- END --------------------

         
