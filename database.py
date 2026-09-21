from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), default='user')
    status = db.Column(db.String(20), default='active')
    face_encoding = db.Column(db.Text)
    profile_picture = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_access = db.Column(db.DateTime)
    
    access_logs = db.relationship('AccessLog', backref='user', lazy=True, cascade='all, delete-orphan')
    schedules = db.relationship('AccessSchedule', backref='user', lazy=True, cascade='all, delete-orphan')

class AccessLog(db.Model):
    __tablename__ = 'access_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    access_time = db.Column(db.DateTime, default=datetime.utcnow)
    access_type = db.Column(db.String(20))
    access_method = db.Column(db.String(20))
    status = db.Column(db.String(20))
    confidence_score = db.Column(db.Float)
    camera_location = db.Column(db.String(100))
    
    # Index untuk query yang sering digunakan
    __table_args__ = (
        db.Index('idx_access_time', 'access_time'),
        db.Index('idx_user_status', 'user_id', 'status'),
    )

class AccessSchedule(db.Model):
    __tablename__ = 'access_schedules'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    day_of_week = db.Column(db.String(20))
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_active = db.Column(db.Boolean, default=True)

class DoorLog(db.Model):
    __tablename__ = 'door_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    door_id = db.Column(db.String(50))
    action = db.Column(db.String(20))
    action_by = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(200))
    
    # Index untuk query yang sering digunakan
    __table_args__ = (
        db.Index('idx_timestamp', 'timestamp'),
        db.Index('idx_door_action', 'door_id', 'action'),
    )

