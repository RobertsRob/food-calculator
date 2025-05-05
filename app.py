from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
import openai
import os
import image_resizor
import secrets
import sqlite3
import json
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import re
from datetime import date

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    username = session.get('username')
    if username is None:
        return redirect(url_for("login"))
    
    # Connect to the database to fetch the user's data
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()

    # Query to get the user data based on the username
    cursor.execute("SELECT name, data FROM users WHERE name = ?", (username,))
    user_data = cursor.fetchone()

    conn.close()

    # If user data exists, pass it to the template
    if user_data:
        name, data = user_data
        try:
            # Преобразуем строку JSON в Python объект
            data = json.loads(data) if data else {}
        except json.JSONDecodeError:
            data = {}
        today = date.today().isoformat()
        return render_template("index.html", username=username, name=name, data=data, today=today, goal_calories=data.get("calories", 0), goal_protein=data.get("protein", 0), goal_carbs=data.get("carbs", 0), goal_fats=data.get("fats", 0))
    else:
        return "User not found.", 404

@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for("login"))


@app.route("/login")
def login():
    login_error = session.pop('login_error', None)
    return render_template("login.html", login_error=login_error)

@app.route("/login_processor", methods=["POST"])
def login_processor():
    username = request.form.get("username")
    password = request.form.get("password")
    if len(username) < 5 or len(password) < 5:
        session['login_error'] = "Username and password must be at least 5 characters long."
        return redirect(url_for("login"))
    
    
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        data TEXT
    )
    ''')

    cursor.execute("SELECT password FROM users WHERE name = ?", (username,))
    row = cursor.fetchone()

    if row is None:
        session['login_error'] = "Incorrect username or password."
        conn.close()
        return redirect(url_for("login"))

    stored_password_hash = row[0]

    # Compare the entered password with stored hash
    if not check_password_hash(stored_password_hash, password):
        session['login_error'] = "Incorrect username or password."
        conn.close()
        return redirect(url_for("login"))

    session['username'] = username
    return redirect(url_for("index"))




@app.route("/signup")
def signup():
    signup_error = session.pop('signup_error', None)
    return render_template("signup.html", signup_error=signup_error)

@app.route("/signup_processor", methods=["POST"])
def signup_processor():
    username = request.form.get("username")
    password = request.form.get("password")
    password_repeat = request.form.get("password_repeat")
    key = request.form.get("key")
    if len(username) < 5 or len(password) < 5 or len(password_repeat) < 5:
        session['signup_error'] = "Username and password must be at least 5 characters long."
        return redirect(url_for("signup"))
    if password != password_repeat:
        session['signup_error'] = "Passwords do not match."
        return redirect(url_for("signup"))
    
    # Check if key exists and is unused
    key_conn = sqlite3.connect("keys.db")
    key_cursor = key_conn.cursor()
    key_cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            used INTEGER DEFAULT 0
        )
    ''')
    key_cursor.execute("SELECT used FROM keys WHERE key = ?", (key,))
    key_data = key_cursor.fetchone()

    if key_data is None:
        session['signup_error'] = "Invalid key."
        key_conn.close()
        return redirect(url_for("signup"))
    
    if key_data[0] == 1:
        session['signup_error'] = "This key has already been used."
        key_conn.close()
        return redirect(url_for("signup"))

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Save user to user_data.db
    user_conn = sqlite3.connect("user_data.db")
    user_cursor = user_conn.cursor()
    user_cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            data TEXT
        )
    ''')

    try:
        # Check if the username already exists
        user_cursor.execute("SELECT COUNT(*) FROM users WHERE name = ?", (username,))
        user_exists = user_cursor.fetchone()[0]

        if user_exists > 0:
            session['signup_error'] = "Username already taken."
            user_conn.close()
            key_conn.close()
            return redirect(url_for("signup"))

        # Proceed with user insertion
        user_cursor.execute('''
            INSERT INTO users (created_at, name, password, data)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            username,
            hashed_password,
            json.dumps({})  # Insert an empty JSON object
        ))
        user_conn.commit()
    except sqlite3.IntegrityError:
        session['signup_error'] = "An error occurred while creating your account."
        user_conn.close()
        key_conn.close()
        return redirect(url_for("signup"))

    # Mark the key as used
    key_cursor.execute("UPDATE keys SET used = 1 WHERE key = ?", (key,))
    key_conn.commit()

    # Clean up
    user_conn.close()
    key_conn.close()

    session['username'] = username
    return redirect(url_for("index"))



@app.route("/key_creator_1262378213", methods=["GET", "POST"], endpoint="key_creator")
def key_creator():
    if session.get("username") != "admin":
        return "Access denied", 403

    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, used INTEGER DEFAULT 0)")

    new_key = None

    if request.method == "POST":
        delete_key = request.form.get("delete_key")

        if not delete_key:
            new_key = secrets.token_urlsafe(12)
            try:
                cursor.execute("INSERT INTO keys (key, used) VALUES (?, 0)", (new_key,))
                conn.commit()
            except sqlite3.IntegrityError:
                print("❌ Key already exists (rare case). Try again.")

        elif delete_key:
            cursor.execute("DELETE FROM keys WHERE key = ?", (delete_key,))
            conn.commit()

    cursor.execute("SELECT key, used FROM keys")
    keys = cursor.fetchall()
    conn.close()

    return render_template("key_creator.html", keys=keys, new_key=new_key)



@app.route("/user_view_21363526231", methods=["GET", "POST"], endpoint="user_view")
def user_view():
    if session.get("username") != "admin":
        return "Access denied", 403

    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()

    if request.method == "POST":
        user_id_to_delete = request.form.get("delete_id")
        if user_id_to_delete:
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id_to_delete,))
            conn.commit()

    cursor.execute("SELECT user_id, name, data, created_at FROM users")
    users = cursor.fetchall()
    conn.close()
    return render_template("user_view.html", users=users)


@app.route("/admin_panel_928736123")
def admin_panel():
    if session.get("username") != "admin":
        return "Access denied", 403
    return render_template("admin_panel.html")
















@app.route("/calculate_macros", methods=["POST"])
def calculate_macros():
    if "username" not in session:
        return redirect(url_for("login"))

    mass = float(request.form.get("mass"))
    height = float(request.form.get("height"))
    activity = request.form.get("activity")

    # Формируем запрос к OpenAI
    prompt = f"""
    A user has the following data:
    Mass: {mass} kg
    Height: {height} cm
    Activity level: {activity} (options: ordinary(light), light sport(normal muscle gain), muscle gain (extreme muscle gain))

    User is commiting to the lean but good bulk.

    Based on this, calculate:
    - Daily calories
    - Daily protein (g)
    - Daily carbs (g)
    - Daily fats (g)

    Based on this, calculate and return ONLY valid JSON (no explanation, no Markdown):
    {{
        "calories": ...,
        "protein": ...,
        "carbs": ...,
        "fats": ...
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }]
            }
        ],
        temperature=0.5,
        max_tokens=1000
    )

    data_raw = response.choices[0].message.content.strip("```")
    json_match = re.search(r"\{[\s\S]*?\}", data_raw)

    if json_match:
        json_string = json_match.group(0)
        try:
            result = json.loads(json_string)
        except json.JSONDecodeError as e:
            print("JSON decode error:", e) 
            print("Raw string was:", json_string)
            return "Failed to parse response", 500
    else:
        print("No JSON found in response:")
        print(data_raw)
        return "No JSON data found in response", 500

    # Добавляем текущую дату в saved_days
    today = datetime.now().date().isoformat()
    result_with_days = result.copy()

    # Сохраняем результат в БД
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()



    username = session.get("username")
    if not username:
        return jsonify({"error": "User not logged in"}), 400

    # Извлекаем текущие данные из базы данных
    cursor.execute("SELECT data FROM users WHERE name = ?", (username,))
    row = cursor.fetchone()

    if row:
        try:
            # Если данные уже есть, парсим их
            existing_data = json.loads(row[0]) if row[0] else {}
        except json.JSONDecodeError:
            existing_data = {}
    else:
        existing_data = {}

    # Обновляем только параметры "calories", "protein", "carbs", "fats"
    if "calories" in result:
        existing_data["calories"] = result["calories"]
    if "protein" in result:
        existing_data["protein"] = result["protein"]
    if "carbs" in result:
        existing_data["carbs"] = result["carbs"]
    if "fats" in result:
        existing_data["fats"] = result["fats"]

    # Сохраняем обновленные данные в базе данных, не трогая saved_days
    cursor.execute(
        "UPDATE users SET data = ? WHERE name = ?",
        (json.dumps(existing_data), username)
    )
    conn.commit()
    conn.close()

    return "", 200












@app.route("/bmi", methods=["POST"])
def home():
    coment = request.files.get("coment")
    image = request.files.get("image")

    if not image:
        return jsonify({"error": "Missing height, weight, or image"}), 400

    image_base64 = image_resizor.resize_image(image, target_size_kb=250)
    print(image_base64)

    prompt_text = (
    "Analyze the food shown in the image and return a JSON with keys: "
    "name (short name of the meal like 'Chicken with rice'), "
    "calories, protein, carbs, fats."
    " Respond with JSON only."
    f"Coment about food: {coment}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You're a food nutrition analyzer. Use object size like forks or hands for portion estimate."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=1000,
        temperature=0.5
    )

    result = response.choices[0].message.content.strip()
    json_match = re.search(r"\{[\s\S]*?\}", result)

    if json_match:
        json_string = json_match.group(0)
        try:
            new_data = json.loads(json_string)
        except json.JSONDecodeError as e:
            print("JSON decode error:", e)
            print("Raw string was:", json_string)
            return "Failed to parse response", 500
    else:
        print("No JSON found in response:")
        print(result)
        return "No JSON data found in response", 500

    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    # Подключаемся к БД
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()

    # Получаем старую data
    cursor.execute("SELECT data FROM users WHERE name = ?", (username,))
    row = cursor.fetchone()
    if row:
        try:
            existing_data = json.loads(row[0]) if row[0] else {}
        except json.JSONDecodeError:
            existing_data = {}
    else:
        existing_data = {}

    # Добавляем сегодняшнюю дату
    today = date.today().isoformat()
    saved_days = existing_data.get("saved_days", {})

    # Готовим формат блюда
    meal_entry = {
        "name": new_data.get("name", "Unnamed meal"),
        "calories": new_data.get("calories", 0),
        "protein": new_data.get("protein", 0),
        "carbs": new_data.get("carbs", 0),
        "fats": new_data.get("fats", 0)
    }

    # Если дата уже есть, добавляем в список
    if today in saved_days:
        day_meals = saved_days[today]
        if isinstance(day_meals, list):
            day_meals.append(meal_entry)
        else:
            # Старый формат (dict) → конвертируем в список
            day_meals = [day_meals, meal_entry]
        saved_days[today] = day_meals
    else:
        saved_days[today] = [meal_entry]

    # Обновляем только saved_days
    existing_data["saved_days"] = saved_days

    # Сохраняем обратно в БД
    cursor.execute(
        "UPDATE users SET data = ? WHERE name = ?",
        (json.dumps(existing_data), username)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "food_result": result
    })








@app.route('/delete_meal', methods=['POST'])
def delete_meal():
    print(1)
    data = request.json
    date = data.get('date')
    meal_index = int(data.get('mealIndex'))  # Convert to integer

    print(data)
    print(date)
    print(meal_index)

    if not date or meal_index is None:
        return jsonify({'error': 'Invalid data'}), 400

    # Логируем полученные данные
    print(f"Received data: date = {date}, meal_index = {meal_index}")

    # Подключаемся к базе данных
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()

    username = session.get("username")
    if not username:
        return jsonify({"error": "User not logged in"}), 400

    cursor.execute("SELECT data FROM users WHERE name = ?", (username,))
    row = cursor.fetchone()

    if row:
        try:
            existing_data = json.loads(row[0]) if row[0] else {}
        except json.JSONDecodeError:
            existing_data = {}
    else:
        existing_data = {}

    saved_days = existing_data.get("saved_days", {})

    if date in saved_days:
        meals = saved_days[date]

        # Check if the meal index is within the range of the meals list
        if 0 <= meal_index < len(meals):
            print(f"Meal to delete: {meals[meal_index]}")  # Логируем удаляемое блюдо

            # Delete the meal at the specified index
            del meals[meal_index]

            # If after deleting, the list becomes empty, delete the date
            if not meals:
                del saved_days[date]

            existing_data["saved_days"] = saved_days

            cursor.execute("UPDATE users SET data = ? WHERE name = ?", (json.dumps(existing_data), username))
            conn.commit()
            conn.close()

            return '', 200
        else:
            # If the index is out of bounds, log the error
            print(f"Meal not found for {date} at index {meal_index}")  # Логируем ошибку
            return jsonify({'error': 'Meal index out of range'}), 400
    else:
        return jsonify({'error': 'Date not found'}), 400








if __name__ == "__main__":
    app.run(debug=True)