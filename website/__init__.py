from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager, current_user, logout_user
from flask_socketio import SocketIO

db = SQLAlchemy()
DB_NAME = "database.db"


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "YOLO MOHAMMAD HAHAHAH"
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['UPLOAD_FOLDER'] = path.join(app.root_path, 'projects')
    db.init_app(app)
    socketio = SocketIO(app)

    def is_instance(value, instance_type):
        return isinstance(value, instance_type)

    app.jinja_env.filters['is_instance'] = is_instance

    from .models import Auth, Tutors, Projects, Clients
    from .views import views
    from .auth import auth
    from .admin import admin

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return Auth.query.get(int(id))

    # socketio.on('connect')
    # def handle_connect():
    #     print("User connected:", current_user.id)

    @socketio.on('disconnect')
    def handle_disconnect():
        user_id = current_user.id
        print("User disconnected:", user_id)
        logout_user()
        session.clear()

    create_db(app)

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/admin')

    return app


def create_db(app):
    if not path.exists(path.join(app.root_path, DB_NAME)):
        db.create_all(app=app)
