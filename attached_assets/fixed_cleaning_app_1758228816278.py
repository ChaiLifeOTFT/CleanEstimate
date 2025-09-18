import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user, UserMixin
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase, relationship, validates, joinedload
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
import uuid
import json
import time
from datetime import datetime, timezone, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import qrcode
from io import BytesIO
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from sqlalchemy import func, Index, text
from sqlalchemy.exc import IntegrityError
import bleach

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
logger = logging.getLogger(__name__)

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Enhanced Configuration
app.config.update({
    "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL", "sqlite:///cleaning_app.db"),
    "SQLALCHEMY_ENGINE_OPTIONS": {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20
    },
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
    "SESSION_COOKIE_SECURE": os.environ.get('FLASK_ENV') == 'production',
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": 'Lax',
    "MAX_CONTENT_LENGTH": int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024)),
    "UPLOAD_FOLDER": 'static/uploads',
})

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Simple rate limiting (use Redis in production)
request_counts = {}

def rate_limit(max_requests=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            now = time.time()
            key = request.remote_addr
            
            request_counts[key] = [
                timestamp for timestamp in request_counts.get(key, [])
                if now - timestamp < window
            ]
            
            if len(request_counts.get(key, [])) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            if key not in request_counts:
                request_counts[key] = []
            request_counts[key].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Security middleware
@app.before_request
def security_headers():
    g.start_time = time.time()

@app.after_request
def add_security_headers(response):
    response.headers.update({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    })
    
    if hasattr(g, 'start_time'):
        response.headers['X-Response-Time'] = str(time.time() - g.start_time)
    
    return response

# Session cleanup
@app.before_request
def cleanup_session():
    if 'job_data' in session:
        job_data = session['job_data']
        if 'created_at' not in job_data:
            job_data['created_at'] = datetime.now().isoformat()
        else:
            created_at = datetime.fromisoformat(job_data['created_at'])
            if datetime.now() - created_at > timedelta(hours=24):
                session.pop('job_data', None)
                session.pop('task_photos', None)

# Models with all fixes
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='cleaner')
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True, index=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    coordinated_jobs = relationship('Job', back_populates='coordinator', lazy='dynamic')
    assigned_tasks = relationship('JobTask', back_populates='assigned_to', lazy='dynamic')
    timers = relationship('Timer', back_populates='user', lazy='dynamic')
    uploaded_photos = relationship('Photo', back_populates='uploaded_by_user', lazy='dynamic')
    team_memberships = relationship('JobTeamMember', back_populates='user', lazy='dynamic')
    activities = relationship('ActivityLog', back_populates='user', lazy='dynamic')
    
    @validates('role')
    def validate_role(self, key, role):
        if role not in ['coordinator', 'cleaner']:
            raise ValueError("Role must be either 'coordinator' or 'cleaner'")
        return role
    
    @validates('email')
    def validate_email(self, key, email):
        if '@' not in email:
            raise ValueError("Invalid email address")
        return email.lower().strip()

    def __repr__(self):
        return f'<User {self.name} ({self.role})>'

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False, index=True)
    job_address = db.Column(db.String(200), nullable=False)
    lot_number = db.Column(db.String(50), nullable=True)
    cleaning_type = db.Column(db.String(50), nullable=False, index=True)
    square_footage = db.Column(db.Integer, nullable=False)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='active', index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    total_estimated_minutes = db.Column(db.Float, default=0)
    total_actual_minutes = db.Column(db.Float, default=0)
    
    coordinator = relationship('User', back_populates='coordinated_jobs')
    team_members = relationship('JobTeamMember', back_populates='job', cascade='all, delete-orphan', lazy='dynamic')
    job_tasks = relationship('JobTask', back_populates='job', cascade='all, delete-orphan', lazy='dynamic')
    photos = relationship('Photo', back_populates='job', cascade='all, delete-orphan', lazy='dynamic')
    activities = relationship('ActivityLog', back_populates='job', cascade='all, delete-orphan', lazy='dynamic')
    
    __table_args__ = (
        Index('idx_job_coordinator_status', 'coordinator_id', 'status'),
    )

    def get_progress_stats(self):
        tasks = self.job_tasks.all()
        total = len(tasks)
        completed = sum(1 for task in tasks if task.status == 'completed')
        return {
            'total_tasks': total,
            'completed_tasks': completed,
            'progress_percent': round((completed / total * 100), 1) if total > 0 else 0
        }

class JobTeamMember(db.Model):
    __tablename__ = 'job_team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='cleaner')
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    job = relationship('Job', back_populates='team_members')
    user = relationship('User', back_populates='team_memberships')
    
    __table_args__ = (
        db.UniqueConstraint('job_id', 'user_id', name='unique_job_user'),
    )

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    instructions = db.Column(db.Text, nullable=False)
    method = db.Column(db.Text, nullable=False)
    materials = db.Column(db.JSON, nullable=False)
    approved_products = db.Column(db.JSON, nullable=False)
    precautions = db.Column(db.Text, nullable=False)
    time_per_100_sqft = db.Column(db.Float, nullable=False)
    cleaning_type = db.Column(db.String(50), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True, index=True)
    
    job_tasks = relationship('JobTask', back_populates='task', lazy='dynamic')

class JobTask(db.Model):
    __tablename__ = 'job_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    task_order = db.Column(db.Integer, nullable=False)
    estimated_minutes = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    lock_version = db.Column(db.Integer, default=0, nullable=False)
    timer_total_seconds = db.Column(db.Integer, default=0)
    
    job = relationship('Job', back_populates='job_tasks')
    task = relationship('Task', back_populates='job_tasks')
    assigned_to = relationship('User', back_populates='assigned_tasks')
    timers = relationship('Timer', back_populates='job_task', cascade='all, delete-orphan', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('job_id', 'task_order', name='unique_job_task_order'),
        Index('idx_job_task_status', 'job_id', 'status'),
    )

    def can_be_claimed_by(self, user_id):
        return (self.status == 'pending' and 
                (self.assigned_to_id is None or self.assigned_to_id == user_id))

    def claim_by_user(self, user_id):
        if not self.can_be_claimed_by(user_id):
            return False, "Task cannot be claimed"
        
        try:
            with db.session.begin_nested():
                locked_task = db.session.query(JobTask).filter(
                    JobTask.id == self.id,
                    JobTask.status == 'pending'
                ).with_for_update(nowait=True).first()
                
                if not locked_task:
                    return False, "Task was already claimed"
                
                locked_task.status = 'claimed'
                locked_task.assigned_to_id = user_id
                locked_task.claimed_at = datetime.now(timezone.utc)
                locked_task.lock_version += 1
                
                activity = ActivityLog(
                    job_id=locked_task.job_id,
                    user_id=user_id,
                    event_type='task_claimed',
                    payload={'task_id': locked_task.task_id, 'job_task_id': locked_task.id}
                )
                db.session.add(activity)
            
            db.session.commit()
            return True, "Task claimed successfully"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Task claim error: {str(e)}")
            return False, "Failed to claim task"

    def release_by_user(self, user_id):
        if self.assigned_to_id != user_id or self.status not in ['claimed', 'blocked']:
            return False, "Task cannot be released"
        
        try:
            self.status = 'pending'
            self.assigned_to_id = None
            self.claimed_at = None
            self.lock_version += 1
            
            activity = ActivityLog(
                job_id=self.job_id,
                user_id=user_id,
                event_type='task_released',
                payload={'task_id': self.task_id, 'job_task_id': self.id}
            )
            db.session.add(activity)
            db.session.commit()
            return True, "Task released successfully"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Task release error: {str(e)}")
            return False, "Failed to release task"

class Timer(db.Model):
    __tablename__ = 'timers'
    
    id = db.Column(db.Integer, primary_key=True)
    job_task_id = db.Column(db.Integer, db.ForeignKey('job_tasks.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False)
    stopped_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, default=0)
    extension_minutes = db.Column(db.Integer, default=0)
    extension_reason = db.Column(db.String(200), nullable=True)
    
    job_task = relationship('JobTask', back_populates='timers')
    user = relationship('User', back_populates='timers')

    @property
    def is_running(self):
        return self.stopped_at is None

    def stop(self):
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)
            self.duration_seconds = int((self.stopped_at - self.started_at).total_seconds())

class Photo(db.Model):
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    job_task_id = db.Column(db.Integer, db.ForeignKey('job_tasks.id'), nullable=True, index=True)
    type = db.Column(db.String(20), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    original_filename = db.Column(db.String(255), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    description = db.Column(db.Text, nullable=True)
    
    job = relationship('Job', back_populates='photos')
    uploaded_by_user = relationship('User', back_populates='uploaded_photos')

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    job = relationship('Job', back_populates='activities')
    user = relationship('User', back_populates='activities')

# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility functions
def sanitize_input(text):
    """Sanitize user input"""
    if not text:
        return text
    return bleach.clean(text, tags=[], strip=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, max_size=None):
    """Safely save uploaded file with validation"""
    if not file or not file.filename:
        return None, "No file provided"
    
    if not allowed_file(file.filename):
        return None, "File type not allowed"
    
    if max_size:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > max_size:
            return None, f"File too large"
    
    try:
        file_extension = secure_filename(file.filename).rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        return filename, None
        
    except Exception as e:
        logger.error(f"File save error: {str(e)}")
        return None, "Failed to save file"

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != required_role:
                flash(f'Access denied. Requires {required_role} role.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Task library (condensed version)
task_library = {
    "Rough Clean": [
        {
            "task": "Clean all tubs and shower pans",
            "time_per_100": 1.2,
            "instructions": "Remove construction debris and protective films",
            "method": "Use appropriate cleaners and scrub pads",
            "materials": ["All-purpose cleaner", "Scrub pads", "Microfiber cloths"],
            "approved_products": ["Zep cleaners", "CLR"],
            "precautions": "Ensure ventilation, test on small area first"
        },
        {
            "task": "Clean window frames and glass",
            "time_per_100": 1.5,
            "instructions": "Clean all window frames and glass surfaces",
            "method": "Use glass cleaner and squeegee technique",
            "materials": ["Glass cleaner", "Squeegee", "Lint-free cloths"],
            "approved_products": ["Zep glass cleaner", "Windex"],
            "precautions": "Work in shade, avoid streaking"
        }
    ],
    "Final Clean": [
        {
            "task": "Final polish of all surfaces",
            "time_per_100": 1.5,
            "instructions": "Achieve showroom-quality finish",
            "method": "Detail clean and polish all surfaces",
            "materials": ["Polish", "Microfiber cloths", "Detail brushes"],
            "approved_products": ["Zep products", "Pledge"],
            "precautions": "Work methodically, check lighting"
        }
    ]
}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from flask_login import login_user
        
        email = sanitize_input(request.form.get('email', '').strip().lower())
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and '//' not in next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = sanitize_input(request.form.get('name', '').strip())
        email = sanitize_input(request.form.get('email', '').strip().lower())
        password = request.form.get('password', '')
        
        if not all([name, email, password]):
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return render_template('register.html')
        
        try:
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role='cleaner'
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            flash('Registration failed.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    from flask_login import logout_user
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_jobs = db.session.query(Job).join(JobTeamMember).filter(
        JobTeamMember.user_id == current_user.id
    ).all()
    
    coordinated_jobs = []
    if current_user.role == 'coordinator':
        coordinated_jobs = Job.query.filter_by(coordinator_id=current_user.id).all()
    
    return render_template('dashboard.html', 
                         user_jobs=user_jobs, 
                         coordinated_jobs=coordinated_jobs)

@app.route('/create_job', methods=['GET', 'POST'])
@role_required('coordinator')
def create_job():
    if request.method == 'POST':
        client_name = sanitize_input(request.form.get('client_name', '').strip())
        job_address = sanitize_input(request.form.get('job_address', '').strip())
        lot_number = sanitize_input(request.form.get('lot_number', '').strip())
        square_footage = request.form.get('square_footage', type=int)
        cleaning_type = sanitize_input(request.form.get('cleaning_type', '').strip())
        
        if not all([client_name, job_address, square_footage, cleaning_type]):
            flash('All required fields must be filled.', 'error')
            return render_template('create_job.html')
        
        try:
            new_job = Job(
                client_name=client_name,
                job_address=job_address,
                lot_number=lot_number,
                cleaning_type=cleaning_type,
                square_footage=square_footage,
                coordinator_id=current_user.id
            )
            db.session.add(new_job)
            db.session.flush()
            
            team_member = JobTeamMember(
                job_id=new_job.id,
                user_id=current_user.id,
                role='coordinator'
            )
            db.session.add(team_member)
            
            # Create tasks from library
            tasks = task_library.get(cleaning_type, [])
            for i, task_data in enumerate(tasks):
                task = Task(
                    name=task_data['task'],
                    instructions=task_data['instructions'],
                    method=task_data['method'],
                    materials=task_data['materials'],
                    approved_products=task_data['approved_products'],
                    precautions=task_data['precautions'],
                    time_per_100_sqft=task_data['time_per_100'],
                    cleaning_type=cleaning_type
                )
                db.session.add(task)
                db.session.flush()
                
                estimated_minutes = (square_footage / 100) * task_data['time_per_100'] + 5
                job_task = JobTask(
                    job_id=new_job.id,
                    task_id=task.id,
                    task_order=i,
                    estimated_minutes=round(estimated_minutes, 1)
                )
                db.session.add(job_task)
            
            db.session.commit()
            flash(f'Job created successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Job creation error: {str(e)}")
            flash('Failed to create job.', 'error')
    
    return render_template('create_job.html')

@app.route('/job/<int:job_id>/tasks')
@login_required
def job_tasks(job_id):
    job = Job.query.get_or_404(job_id)
    
    is_coordinator = (current_user.role == 'coordinator' and job.coordinator_id == current_user.id)
    is_team_member = JobTeamMember.query.filter_by(
        job_id=job_id, user_id=current_user.id
    ).first() is not None
    
    if not (is_coordinator or is_team_member):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    
    job_tasks = JobTask.query.options(
        joinedload(JobTask.task),
        joinedload(JobTask.assigned_to)
    ).filter_by(job_id=job_id).order_by(JobTask.task_order).all()
    
    return render_template('job_tasks.html', 
                         job=job, 
                         job_tasks=job_tasks,
                         is_coordinator=is_coordinator)

@app.route('/claim_task/<int:job_task_id>', methods=['POST'])
@login_required
@rate_limit(max_requests=5, window=60)
def claim_task(job_task_id):
    if current_user.role != 'cleaner':
        return jsonify({'error': 'Only cleaners can claim tasks'}), 403
    
    job_task = JobTask.query.get_or_404(job_task_id)
    
    team_member = JobTeamMember.query.filter_by(
        job_id=job_task.job_id, user_id=current_user.id
    ).first()
    
    if not team_member:
        return jsonify({'error': 'Not authorized'}), 403
    
    success, message = job_task.claim_by_user(current_user.id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 409

@app.route('/