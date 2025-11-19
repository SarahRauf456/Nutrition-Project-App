import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime, timedelta
import plotly.express as px
import os
st.set_page_config(page_title="AI NutriHealth Analyzer", page_icon="🥗", layout="wide")

# Gradient theme styling
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #80FFDB, #5390D9, #6930C3);
    background-size: 400% 400%;
    animation: gradientBG 12s ease infinite;
}
@keyframes gradientBG {
    0% {background-position: 0% 50%;}
    50% {background-position: 100% 50%;}
    100% {background-position: 0% 50%;}
}
div.block-container{
    background-color: rgba(255,255,255,0.82);
    border-radius: 15px;
    padding: 2rem;
}
</style>
""", unsafe_allow_html=True)


if not os.path.exists("data"):
    os.makedirs("data")

conn = sqlite3.connect("data/nutriapp.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
    email TEXT PRIMARY KEY,
    name TEXT,
    age INT,
    height REAL,
    weight REAL,
    gender TEXT,
    goal TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS water_logs(
    email TEXT, amount INT, timestamp DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS meals(
    email TEXT, meal TEXT, calories INT, protein REAL, carbs REAL, fats REAL, timestamp DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS exercises(
    email TEXT, category TEXT, duration INT, calories_burned INT, timestamp DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS sleep_logs(
    email TEXT, hours REAL, timestamp DATETIME
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS habits(
    email TEXT, habit TEXT, last_completed DATETIME, streak INT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS auth_codes(
    email TEXT, code TEXT, created DATETIME
)""")

conn.commit()

client = None
if "OPENAI_API_KEY" in os.environ:
    client = OpenAI()


def send_magic_code(email):
    code = str(random.randint(100000, 999999))
    cur.execute("INSERT INTO auth_codes VALUES(?,?,?)", (email, code, datetime.now()))
    conn.commit()
    return code

def login():
    st.title("🔐 Login to NutriHealth AI")
    email = st.text_input("Enter your Email")
    if st.button("Send Login Code"):
        if email:
            code = send_magic_code(email)
            st.success(f"Demo mode: your verification code is *{code}*")
            st.session_state["pending_email"] = email

    if "pending_email" in st.session_state:
        user_code = st.text_input("Enter the 6-digit code")
        if st.button("Verify"):
            cur.execute("SELECT code FROM auth_codes WHERE email=? ORDER BY created DESC LIMIT 1",
                        (st.session_state["pending_email"],))
            record = cur.fetchone()
            if record and record[0] == user_code:
                st.session_state["email"] = st.session_state["pending_email"]
                st.experimental_rerun()
            else:
                st.error("Invalid code")

if "email" not in st.session_state:
    login()
    st.stop()


st.sidebar.title("📍 Navigation")
page = st.sidebar.radio("Go to", [
    "Dashboard", "Profile", "Hydration", "Nutrition", "Exercises",
    "Sleep & Habits", "Diet Planner", "Medical Advisor", "AI Chatbot"
])

email = st.session_state["email"]


if page == "Profile":
    st.header("👤 Profile Settings")

    name = st.text_input("Full Name")
    age = st.number_input("Age", 1, 120)
    height = st.number_input("Height (cm)")
    weight = st.number_input("Weight (kg)")
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    goal = st.selectbox("Health Goal", ["Weight Loss", "Muscle Gain", "Maintain Health"])

    if st.button("Save Profile"):
        cur.execute("REPLACE INTO users VALUES(?,?,?,?,?,?,?)",
                    (email, name, age, height, weight, gender, goal))
        conn.commit()
        st.success("Profile Updated")


if page == "Hydration":
    st.header("💧 Water Intake Tracker")
    amount = st.number_input("Water consumed (ml)", 0, 5000)
    if st.button("Add Log"):
        cur.execute("INSERT INTO water_logs VALUES(?,?,?)",
                    (email, amount, datetime.now()))
        conn.commit()
        st.success("Saved!")

    df = pd.read_sql_query(f"SELECT * FROM water_logs WHERE email='{email}'", conn)
    if not df.empty:
        st.subheader("Hydration Chart")
        fig = px.line(df, x="timestamp", y="amount", title="Water Intake Over Time")
        st.plotly_chart(fig, use_container_width=True)


if page == "Nutrition":
    st.header("🥗 Nutrition Tracker")
    meal = st.text_input("Meal Name")
    calories = st.number_input("Calories", 0, 2000)
    protein = st.number_input("Protein (g)", 0, 200)
    carbs = st.number_input("Carbs (g)", 0, 400)
    fats = st.number_input("Fats (g)", 0, 200)

    if st.button("Add Meal"):
        cur.execute("INSERT INTO meals VALUES(?,?,?,?,?,?,?)",
                    (email, meal, calories, protein, carbs, fats, datetime.now()))
        conn.commit()
        st.success("Meal Logged")

    df = pd.read_sql_query(f"SELECT * FROM meals WHERE email='{email}'", conn)
    if not df.empty:
        st.subheader("Nutrition Summary")
        fig = px.bar(df, x="timestamp", y="calories", title="Calories Over Time")
        st.plotly_chart(fig, use_container_width=True)


if page == "Exercises":
    st.header("🏋 Exercise Tracker")
    category = st.selectbox("Exercise Category", ["Hands", "Legs", "Core", "Back", "Full Body"])
    duration = st.number_input("Duration (minutes)", 0, 200)
    calories_burned = duration * 8

    if st.button("Add Workout"):
        cur.execute("INSERT INTO exercises VALUES(?,?,?,?)",
                    (email, category, duration, calories_burned, datetime.now()))
        conn.commit()
        st.success("Exercise Logged")


if page == "Sleep & Habits":
    st.header("😴 Sleep Tracker")
    hours = st.number_input("Hours Slept", 0, 24)
    if st.button("Save Sleep"):
        cur.execute("INSERT INTO sleep_logs VALUES(?,?,?)",
                    (email, hours, datetime.now()))
        conn.commit()
        st.success("Sleep saved")


if page == "Diet Planner":
    st.header("📅 Balanced Diet Generator")
    meals = ["Oats & Fruits", "Chicken Brown Rice", "Vegetable Soup", "Paneer Salad",
             "Protein Smoothie", "Tofu Quinoa", "Egg Sandwich"]

    if st.button("Generate 7-Day Plan"):
        plan = random.sample(meals, 7)
        for i, m in enumerate(plan):
            st.write(f"Day {i+1}: *{m}*")

if page == "Medical Advisor":
    st.header("🩺 Symptom-based Home Remedy Advisor")
    symptom = st.text_area("Describe what you're feeling (e.g., headache, acidity, weakness)")
    if st.button("Get Advice"):
        st.info("Disclaimer: This is not medical diagnosis. Seek a doctor if symptoms persist.")
        st.success(f"Possible causes: Stress / dehydration / vitamin deficiency\n\nHome remedy: Drink water, rest, apply warm compress.\n\nWarning signs: severe pain, breathing difficulty.")


if page == "AI Chatbot":
    st.header("🤖 AI Health & Nutrition Chatbot")
    query = st.text_input("Ask anything about fitness, food, habits…")
    if st.button("Ask"):
        if client:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":"You are a nutrition & fitness expert."},
                          {"role":"user","content":query}]
            )
            st.write(response.choices[0].message["content"])
        else:
            st.write("AI is disabled, add OPENAI_API_KEY")
