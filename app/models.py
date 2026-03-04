from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    """User account model"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship: one user can have many tasks
    tasks = db.relationship('Task', backref='owner', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Task(db.Model):
    """Task model"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Priority: 1=Low, 2=Medium, 3=High
    priority = db.Column(db.Integer, default=2)
    
    # Status: pending, in_progress, completed
    status = db.Column(db.String(20), default='pending')

    # Percent complete (0–100) for richer progress UI and Gantt views
    percent_complete = db.Column(db.Integer, default=0)

    # Flag to mark this task as a milestone in milestone views
    is_milestone = db.Column(db.Boolean, default=False)
    
    # Category/Tag
    category = db.Column(db.String(50), nullable=True)
    
    # Dates
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Foreign key linking to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    @property
    def priority_label(self):
        """Get human-readable priority"""
        priorities = {1: 'Low', 2: 'Medium', 3: 'High'}
        return priorities.get(self.priority, 'Medium')
    
    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.due_date and self.status != 'completed':
            return datetime.utcnow() > self.due_date
        return False


class TaskDependency(db.Model):
    """Relationship between two tasks for Gantt dependencies.

    dependency_type values:
        - 'FS' = Finish to Start
        - 'SS' = Start to Start
        - 'SF' = Start to Finish
        - 'FF' = Finish to Finish
    """
    id = db.Column(db.Integer, primary_key=True)
    predecessor_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    successor_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    dependency_type = db.Column(db.String(2), nullable=False, default='FS')

    predecessor = db.relationship('Task', foreign_keys=[predecessor_id], backref='outgoing_dependencies')
    successor = db.relationship('Task', foreign_keys=[successor_id], backref='incoming_dependencies')

    def __repr__(self):
        return f'<TaskDependency {self.predecessor_id}->{self.successor_id} ({self.dependency_type})>'