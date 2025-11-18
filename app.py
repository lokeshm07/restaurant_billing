from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from mysql.connector import Error
import os
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')


# ---------- REUSABLE FUNCTION WITH AUTO-RECONNECT ----------
def get_db_connection(retries=3, delay=2):
    """
    Connect to MySQL with automatic retry if the connection fails.
    Prevents 'Lost connection to MySQL server during query' errors.
    """
    for attempt in range(retries):
        try:
            connection = mysql.connector.connect(
                host=os.environ.get('DB_HOST', 'lokeshm07.mysql.pythonanywhere-services.com'),
                user=os.environ.get('DB_USER', 'lokeshm07'),
                password=os.environ.get('DB_PASSWORD', 'root12345'),
                database=os.environ.get('DB_NAME', 'lokeshm07$default'),
                connection_timeout=10,
                autocommit=True
            )
            if connection.is_connected():
                return connection
        except Error as e:
            print(f"⚠️ Connection attempt {attempt+1} failed: {e}")
            time.sleep(delay)
    print("❌ Could not connect to MySQL after retries.")
    return None


# ---------- ROUTES ----------
@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db_connection()
    if db is None:
        return "⚠️ Database temporarily unavailable. Please refresh or try again in a few seconds."

    cursor = db.cursor()
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(100) UNIQUE,
            mobile VARCHAR(15)
        )
    """)

    if request.method == 'POST':
        email = request.form['email']
        mobile = request.form['mobile']

        try:
            # Check connection health before query
            db.ping(reconnect=True, attempts=3, delay=2)

            cursor.execute("SELECT * FROM staff WHERE email=%s", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.execute("INSERT INTO staff (email, mobile) VALUES (%s, %s)", (email, mobile))

            session['email'] = email
            session['mobile'] = mobile
            return redirect(url_for('billing'))

        except Error as err:
            print("❌ MySQL query error:", err)
            # Retry once if lost connection mid-query
            if "Lost connection" in str(err):
                print("🔁 Retrying query after lost connection...")
                db = get_db_connection()
                if db:
                    cursor = db.cursor()
                    cursor.execute("INSERT INTO staff (email, mobile) VALUES (%s, %s)", (email, mobile))
                    return redirect(url_for('billing'))
            return f"Database Error: {err}"

        finally:
            cursor.close()
            db.close()

    return render_template('login.html')


@app.route('/billing')
def billing():
    if 'email' not in session:
        return redirect(url_for('login'))

    db = get_db_connection()
    if db is None:
        return "⚠️ Database unavailable. Please refresh."

    try:
        db.ping(reconnect=True, attempts=3, delay=2)
        cursor = db.cursor()
        cursor.execute("SELECT email, mobile FROM staff")
        all_staff = cursor.fetchall()
        return render_template('index.html', email=session['email'], mobile=session['mobile'], staff=all_staff)

    except Error as err:
        print("❌ MySQL error in /billing:", err)
        return "⚠️ Database lost connection. Try again."

    finally:
        cursor.close()
        db.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- RUN ----------
if __name__ == "__main__":
    # threaded=True allows multiple users without crash
    app.run(debug=True, threaded=True)
