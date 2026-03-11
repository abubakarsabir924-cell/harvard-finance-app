import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    # Database se user ke stocks uthao
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0", user_id)

    # Cash balance uthao
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # Total calculate karo
    total_value = cash
    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["total"] = stock["price"] * stock["total_shares"]
        total_value += stock["total"]

    return render_template("index.html", stocks=stocks, cash=cash, total_value=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide symbol", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("shares must be a positive integer", 400)

        if shares <= 0:
            return apology("shares must be positive", 400)

        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        total_cost = stock["price"] * shares

        if user_cash < total_cost:
            return apology("not enough cash", 400)

        # Transaction execute karo
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total_cost, user_id)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                   user_id, symbol, shares, stock["price"])

        flash("Bought!")
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC", user_id)
    return render_template("history.html", transactions=transactions)
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC", user_id)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide symbol", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", stock=stock)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation:
            return apology("must provide all fields", 400)
        if password != confirmation:
            return apology("passwords do not match", 400)

        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
        except:
            return apology("username already exists", 400)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        user_shares = db.execute("SELECT SUM(shares) as total FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)[0]["total"]

        if shares <= 0 or shares > user_shares:
            return apology("invalid shares", 400)

        stock = lookup(symbol)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                   user_id, symbol, -shares, stock["price"])
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", stock["price"] * shares, user_id)

        flash("Sold!")
        return redirect("/")
    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)
        return render_template("sell.html", symbols=symbols)
