from datetime import datetime
from . import db
from flask_login import UserMixin

# https://youtu.be/uZqO_PoLDi8
# https://youtu.be/mCy52I4exTU
# https://youtu.be/yBDHkveJUf4


class Auth(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tutors(db.Model):
    # ID	Name	Department	No.	Email
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    department = db.Column(db.String(20))
    number = db.Column(db.String(20))
    email = db.Column(db.String(50), unique=True)
    projects = db.relationship('Projects', backref='tutor', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Projects(db.Model):
    # ID	Name	Department	DueDate 	Price(client)	Price(tutor)	STATUS	TutorID	ClientID	FileTUTOR  FileCLIENT
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    department = db.Column(db.String(20))
    description = db.Column(db.String(150))
    due = db.Column(db.DateTime(timezone=True))
    gain = db.Column(db.Float)
    price = db.Column(db.Float)
    status = db.Column(db.String(15))
    tutor_id = db.Column(db.Integer, db.ForeignKey('tutors.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    fileTutor = db.Column(db.String(50))
    fileClient = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    at_tutor = db.Column(db.DateTime)
    at_client = db.Column(db.DateTime)
    tutors_received = db.Column(db.PickleType)

    def add_tutor_received(self, tutor_id):
        if self.tutors_received is None:
            self.tutors_received = set()
        self.tutors_received.add(tutor_id)
        db.session.commit()

    def get_tutors_received(self):
        if self.tutors_received is None:
            return set()
        return self.tutors_received


class Clients(db.Model):
    # ID	Name	Uni	Deparment	Nb.	Email
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    university = db.Column(db.String(20))
    department = db.Column(db.String(20))
    number = db.Column(db.String(20))
    email = db.Column(db.String(50), unique=True)
    projects = db.relationship('Projects', backref='client', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
