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
from models import db, User, Key  # предполагаем, что User определён как модель
from zoneinfo import ZoneInfo


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
load_dotenv()

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")  # Render adds this automatically
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    username = session.get('username')
    if username is None:
        return redirect(url_for("login"))

    user = User.query.filter_by(name=username).first()

    if user:
        try:
            data = json.loads(user.data) if user.data else {}
        except json.JSONDecodeError:
            data = {}

        # today = date.today().isoformat()
        today = datetime.now(ZoneInfo("Europe/Riga")).date().isoformat()
        return render_template(
            "index.html",
            username=username,
            name=user.name,
            data=data,
            today=today,
            goal_calories=data.get("calories", 0),
            goal_protein=data.get("protein", 0),
            goal_carbs=data.get("carbs", 0),
            goal_fats=data.get("fats", 0)
        )
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

    # Создание таблиц, если их ещё нет
    db.create_all()

    user = User.query.filter_by(name=username).first()

    if not user or not check_password_hash(user.password, password):
        session['login_error'] = "Incorrect username or password."
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
    key_value = request.form.get("key")

    if len(username) < 5 or len(password) < 5 or len(password_repeat) < 5:
        session['signup_error'] = "Username and password must be at least 5 characters long."
        return redirect(url_for("signup"))

    if password != password_repeat:
        session['signup_error'] = "Passwords do not match."
        return redirect(url_for("signup"))

    db.create_all()

    # Проверка ключа
    key = Key.query.filter_by(key=key_value).first()
    if not key:
        session['signup_error'] = "Invalid key."
        return redirect(url_for("signup"))
    if key.used:
        session['signup_error'] = "This key has already been used."
        return redirect(url_for("signup"))

    # Проверка имени
    if User.query.filter_by(name=username).first():
        session['signup_error'] = "Username already taken."
        return redirect(url_for("signup"))

    try:
        hashed_password = generate_password_hash(password)
        new_user = User(
            name=username,
            password=hashed_password,
            data=json.dumps({})
        )
        db.session.add(new_user)

        key.used = True
        db.session.commit()

        session['username'] = username
        return redirect(url_for("index"))
    except Exception as e:
        db.session.rollback()
        session['signup_error'] = "An error occurred while creating your account."
        return redirect(url_for("signup"))



@app.route("/key_creator_1262378213", methods=["GET", "POST"], endpoint="key_creator")
def key_creator():
    # if session.get("username") != "admin":
    #     return "Access denied", 403

    new_key = None

    if request.method == "POST":
        delete_key = request.form.get("delete_key")

        if not delete_key:
            new_key = secrets.token_urlsafe(12)
            if not Key.query.get(new_key):  # check if key already exists
                new_key_entry = Key(key=new_key, used=False)
                db.session.add(new_key_entry)
                db.session.commit()
            else:
                print("❌ Key already exists (rare case). Try again.")
        else:
            Key.query.filter_by(key=delete_key).delete()
            db.session.commit()

    keys = Key.query.all()

    return render_template("key_creator.html", keys=keys, new_key=new_key)





@app.route("/user_view_21363526231", methods=["GET", "POST"], endpoint="user_view")
def user_view():
    # if session.get("username") != "admin":
    #     return "Access denied", 403

    if request.method == "POST":
        user_id_to_delete = request.form.get("delete_id")
        if user_id_to_delete:
            # Удаление пользователя из базы данных с использованием SQLAlchemy
            user = User.query.filter_by(user_id=user_id_to_delete).first()
            if user:
                db.session.delete(user)
                db.session.commit()

    # Получаем список всех пользователей
    users = User.query.all()
    return render_template("user_view.html", users=users)


@app.route("/admin_panel_928736123")
def admin_panel():
    # if session.get("username") != "admin":
    #     return "Access denied", 403
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

    username = session.get("username")
    if not username:
        return jsonify({"error": "User not logged in"}), 400

    # Используем SQLAlchemy для извлечения данных
    user = User.query.filter_by(name=username).first()

    if user:
        try:
            existing_data = json.loads(user.data) if user.data else {}
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
    user.data = json.dumps(existing_data)
    db.session.commit()

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
    f"True information about food from user that you can use to analyse it: {coment}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You're a food nutrition analyzer. Use object size like forks or hands for portion estimate. Also use user given information about food!"
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
            return "Failed to parse response", 500
    else:
        print("No JSON found in response:")
        return "No JSON data found in response", 500

    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    # Get user from database using SQLAlchemy
    user = User.query.filter_by(name=username).first()

    if not user:
        return "User not found.", 404

    # Parse the user's existing data
    try:
        existing_data = json.loads(user.data) if user.data else {}
    except json.JSONDecodeError:
        existing_data = {}

    # Add today's date
    today = date.today().isoformat()
    saved_days = existing_data.get("saved_days", {})

    # Prepare the meal entry
    meal_entry = {
        "name": new_data.get("name", "Unnamed meal"),
        "calories": new_data.get("calories", 0),
        "protein": new_data.get("protein", 0),
        "carbs": new_data.get("carbs", 0),
        "fats": new_data.get("fats", 0)
    }

    # If today's date exists, append to the list of meals
    if today in saved_days:
        day_meals = saved_days[today]
        if isinstance(day_meals, list):
            day_meals.append(meal_entry)
        else:
            # Convert the old format (dict) to a list
            day_meals = [day_meals, meal_entry]
        saved_days[today] = day_meals
    else:
        saved_days[today] = [meal_entry]

    # Update the saved_days in the existing data
    existing_data["saved_days"] = saved_days

    # Save the updated data back into the database
    user.data = json.dumps(existing_data)
    db.session.commit()

    return jsonify({
        "food_result": result
    })








@app.route('/delete_meal', methods=['POST'])
def delete_meal():
    data = request.json
    date = data.get('date')
    meal_index = int(data.get('mealIndex'))  # Convert to integer

    if not date or meal_index is None:
        return jsonify({'error': 'Invalid data'}), 400

    # Логируем полученные данные
    print(f"Received data: date = {date}, meal_index = {meal_index}")

    username = session.get("username")
    if not username:
        return jsonify({"error": "User not logged in"}), 400

    # Get user from database using SQLAlchemy
    user = User.query.filter_by(name=username).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        existing_data = json.loads(user.data) if user.data else {}
    except json.JSONDecodeError:
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

            # Update user data in the database
            user.data = json.dumps(existing_data)
            db.session.commit()

            return '', 200
        else:
            # If the index is out of bounds, log the error
            print(f"Meal not found for {date} at index {meal_index}")  # Логируем ошибку
            return jsonify({'error': 'Meal index out of range'}), 400
    else:
        return jsonify({'error': 'Date not found'}), 400






with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)

