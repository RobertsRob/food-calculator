from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    name = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    data = db.Column(db.Text)


class Key(db.Model):
    __tablename__ = 'keys'

    key = db.Column(db.String(255), primary_key=True)
    used = db.Column(db.Boolean, default=False)