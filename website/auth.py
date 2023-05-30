from flask import Blueprint, render_template, redirect, request, flash, url_for, session
import bcrypt
from .models import Auth
from flask_login import login_user, login_required, logout_user, current_user

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=["POST", "GET"])
def login():
    print(current_user)
    print(current_user.is_authenticated)
    if request.method == "POST":
        username = request.form.get("inputUsername")
        password = request.form.get("inputPassword")
        # query for username in db, then compare hashed to queried password
        # if username name does not exist or password is not equal:
        auth = Auth.query.filter_by(username=username).first()
        if auth:
            hashed = auth.password
            if bcrypt.checkpw(password.encode('utf-8'), hashed):
                login_user(auth)
                session.permanent = False
                print(auth)
                return redirect('/')
            else:
                flash("USERNAME OR PASSWORD DO NOT MATCH", category="fail")
        else:
            flash("USERNAME OR PASSWORD DO NOT MATCH", category="fail")
    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    print("Logging out:", current_user)
    logout_user()
    session.clear()
    print("Logged out:", current_user)
    return redirect(url_for('auth.login'))
