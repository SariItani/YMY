import bcrypt
from flask import Blueprint, flash, redirect, render_template, request, url_for
from .models import Auth
from . import db

admin = Blueprint('admin', __name__)


@admin.route('/', methods=["POST", "GET"])
def add_employee():
    if request.method == "POST":
        username = request.form.get("inputUsername")
        password = request.form.get("inputPassword")
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        # save hashedpassword and username in a new db entry
        user = Auth.query.filter_by(username=username).first()
        if user:
            flash("USERNAME TAKEN", category="fail")
        else:
            new_user = Auth(username=username, password=hashed)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('auth.login'))
    return render_template('create_user.html')
