from flask import Flask, render_template, request, redirect, url_for, flash, session
import json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change_this_secret_to_anything"  # change for production

USERS_FILE = "users.json"

# ---------- JSON persistence helpers ----------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

# ensure file exists
users = load_users()
save_users(users)

# ---------- ROUTES ----------
@app.route('/')
def index():
    # Show welcome. If user already logged-in, redirect to dashboard
    if session.get("username"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route('/register', methods=['GET','POST'])
def register():
    users = load_users()
    if request.method == 'POST':
        fullname = request.form.get('fullname','').strip()
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        password = request.form.get('password','')
        try:
            initial_deposit = int(request.form.get('initial_deposit', 0))
        except ValueError:
            initial_deposit = 0

        if not fullname or not username or not email or not password:
            flash("Please fill required fields.", "error")
            return redirect(url_for('register'))

        if username in users:
            flash("Username already exists. Choose another.", "error")
            return redirect(url_for('register'))

        users[username] = {
            "fullname": fullname,
            "email": email,
            "phone": phone,
            "password": password,
            "balance": initial_deposit,
            "transactions": []
        }

        if initial_deposit > 0:
            users[username]["transactions"].append({
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "Deposit",
                "amount": initial_deposit,
                "balance": initial_deposit
            })

        save_users(users)
        session["username"] = username
        flash(f"Account created for {username}.", "success")
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    # If already logged in, show dashboard
    if 'username' in session:
        return redirect(url_for('dashboard'))

    users = load_users()
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        user = users.get(username)
        if user and user.get('password') == password:
            session['username'] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    users = load_users()
    username = session.get("username")
    if not username:
        flash("Please login first.", "error")
        return redirect(url_for('login'))
    user = users.get(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    total_deposits = sum(t["amount"] for t in user.get("transactions", []) if t["type"].lower() == "deposit")
    total_withdrawals = sum(t["amount"] for t in user.get("transactions", []) if t["type"].lower() == "withdraw")
    return render_template("dashboard.html",
                           username=username,
                           fullname=user.get("fullname",""),
                           email=user.get("email",""),
                           phone=user.get("phone",""),
                           balance=user.get("balance",0),
                           total_deposits=total_deposits,
                           total_withdrawals=total_withdrawals)

# deposit
@app.route('/deposit', methods=['POST'])
def deposit():
    users = load_users()
    username = session.get("username")
    if not username:
        flash("Please login to deposit.", "error")
        return redirect(url_for('login'))

    user = users.get(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    try:
        amount = int(request.form.get('amount',0))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash("Enter a valid amount to deposit.", "error")
        return redirect(url_for('dashboard'))

    user['balance'] = user.get('balance',0) + amount
    user['transactions'].append({
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "Deposit",
        "amount": amount,
        "balance": user['balance']
    })
    users[username] = user
    save_users(users)
    flash(f"✅ Deposit successful! ₹{amount} added.", "success")
    return redirect(url_for('dashboard'))

# withdraw with limit and insufficient check
WITHDRAW_LIMIT = 5000

@app.route('/withdraw', methods=['POST'])
def withdraw():
    users = load_users()
    username = session.get("username")
    if not username:
        flash("Please login to withdraw.", "error")
        return redirect(url_for('login'))
    user = users.get(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    try:
        amount = int(request.form.get('amount',0))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash("Enter a valid amount.", "error")
        return redirect(url_for('dashboard'))

    if amount > WITHDRAW_LIMIT:
        flash(f"❌ Withdrawal limit reached — max ₹{WITHDRAW_LIMIT} per transaction.", "error")
        return redirect(url_for('dashboard'))

    if amount > user.get('balance',0):
        flash("❌ Insufficient balance!", "error")
        return redirect(url_for('dashboard'))

    user['balance'] = user.get('balance',0) - amount
    user['transactions'].append({
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "Withdraw",
        "amount": amount,
        "balance": user['balance']
    })
    users[username] = user
    save_users(users)
    flash(f"✅ Withdrawal successful! ₹{amount} withdrawn.", "success")
    return redirect(url_for('dashboard'))

@app.route('/transactions')
def transactions():
    users = load_users()
    username = session.get("username")
    if not username:
        flash("Please login to view transactions.", "error")
        return redirect(url_for('login'))
    user = users.get(username)
    txns = user.get('transactions',[]) if user else []
    txns = list(reversed(txns))  # newest first
    return render_template('transaction.html', username=username, transactions=txns)

# optional: change password route
@app.route('/change_password', methods=['POST'])
def change_password():
    users = load_users()
    username = session.get('username')
    if not username:
        flash("Please login.", "error")
        return redirect(url_for('login'))
    user = users.get(username)
    current = request.form.get("current_password","")
    newp = request.form.get("new_password","")
    if user.get("password") != current:
        flash("Current password incorrect.", "error")
    else:
        user["password"] = newp
        users[username] = user
        save_users(users)
        flash("Password changed successfully.", "success")
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)