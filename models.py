from app import db
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy import func, Index
from sqlalchemy.orm import validates


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default='cleaner')  # 'coordinator' or 'cleaner'
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    coordinated_jobs = db.relationship('Job', backref='coordinator', lazy=True, foreign_keys='Job.coordinator_id')
    assigned_tasks = db.relationship('JobTask', backref='assigned_to', lazy=True, foreign_keys='JobTask.assigned_to_id')
    timers = db.relationship('Timer', backref='user', lazy=True)
    uploaded_photos = db.relationship('Photo', backref='uploaded_by_user', lazy=True, foreign_keys='Photo.uploaded_by_id')
    
    @validates('role')
    def validate_role(self, key, role):
        if role not in ['coordinator', 'cleaner']:
            raise ValueError("Role must be either 'coordinator' or 'cleaner'")
        return role

    def __repr__(self):
        return f'<User {self.name} ({self.role})>'


class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    job_address = db.Column(db.String(200), nullable=False)
    lot_number = db.Column(db.String(50), nullable=True)
    cleaning_type = db.Column(db.String(50), nullable=False)
    square_footage = db.Column(db.Integer, nullable=False)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='active')  # 'active', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    total_estimated_minutes = db.Column(db.Float, default=0)
    total_actual_minutes = db.Column(db.Float, default=0)
    
    # Relationships
    team_members = db.relationship('JobTeamMember', backref='job', lazy=True, cascade='all, delete-orphan')
    job_tasks = db.relationship('JobTask', backref='job', lazy=True, cascade='all, delete-orphan')
    photos = db.relationship('Photo', backref='job', lazy=True, cascade='all, delete-orphan')
    activities = db.relationship('ActivityLog', backref='job', lazy=True, cascade='all, delete-orphan')
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in ['active', 'completed', 'cancelled']:
            raise ValueError("Status must be 'active', 'completed', or 'cancelled'")
        return status

    def __repr__(self):
        return f'<Job {self.client_name} - {self.cleaning_type}>'


class JobTeamMember(db.Model):
    __tablename__ = 'job_team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='cleaner')  # 'coordinator' or 'cleaner'
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref='team_memberships')
    
    __table_args__ = (
        db.UniqueConstraint('job_id', 'user_id', name='unique_job_user'),
        Index('idx_job_team_lookup', 'job_id', 'user_id'),
    )

    @validates('role')
    def validate_role(self, key, role):
        if role not in ['coordinator', 'cleaner']:
            raise ValueError("Role must be either 'coordinator' or 'cleaner'")
        return role


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    method = db.Column(db.Text, nullable=False)
    materials = db.Column(db.JSON, nullable=False)  # List of materials
    approved_products = db.Column(db.JSON, nullable=False)  # List of approved products
    precautions = db.Column(db.Text, nullable=False)
    time_per_100_sqft = db.Column(db.Float, nullable=False)
    cleaning_type = db.Column(db.String(50), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    job_tasks = db.relationship('JobTask', backref='task', lazy=True)

    def __repr__(self):
        return f'<Task {self.name} ({self.cleaning_type})>'


class JobTask(db.Model):
    __tablename__ = 'job_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    task_order = db.Column(db.Integer, nullable=False)  # Order in the job sequence
    estimated_minutes = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'claimed', 'in_progress', 'blocked', 'completed'
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    lock_version = db.Column(db.Integer, default=0, nullable=False)  # Optimistic locking
    timer_total_seconds = db.Column(db.Integer, default=0)
    before_photo_id = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=True)
    after_photo_id = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=True)
    
    # Relationships
    timers = db.relationship('Timer', backref='job_task', lazy=True, cascade='all, delete-orphan')
    before_photo = db.relationship('Photo', foreign_keys=[before_photo_id], post_update=True)
    after_photo = db.relationship('Photo', foreign_keys=[after_photo_id], post_update=True)
    
    __table_args__ = (
        # Ensure only one active claim per job task
        Index('idx_unique_active_claim', 'job_id', 'task_id', unique=True, 
              postgresql_where=db.text("status IN ('claimed', 'in_progress')")),
        Index('idx_job_task_status', 'job_id', 'status'),
        Index('idx_job_task_assigned', 'job_id', 'assigned_to_id'),
    )

    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = ['pending', 'claimed', 'in_progress', 'blocked', 'completed']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return status

    def can_be_claimed_by(self, user_id):
        """Check if this task can be claimed by a user"""
        return (self.status == 'pending' and 
                (self.assigned_to_id is None or self.assigned_to_id == user_id))

    def claim_by_user(self, user_id):
        """Attempt to claim this task for a user with robust conflict prevention"""
        if not self.can_be_claimed_by(user_id):
            return False, "Task cannot be claimed"
            
        try:
            # Use pessimistic locking to prevent race conditions
            from sqlalchemy import and_
            locked_task = db.session.query(JobTask).filter(
                and_(
                    JobTask.id == self.id,
                    JobTask.lock_version == self.lock_version,
                    JobTask.status == 'pending'
                )
            ).with_for_update().first()
            
            if not locked_task:
                return False, "Task was already claimed by another user"
            
            # Update task atomically
            locked_task.status = 'claimed'
            locked_task.assigned_to_id = user_id
            locked_task.claimed_at = datetime.now(timezone.utc)
            locked_task.lock_version += 1
            
            # Log the claiming activity
            from models import ActivityLog
            activity = ActivityLog(
                job_id=locked_task.job_id,
                user_id=user_id,
                event_type='task_claimed',
                payload={
                    'task_id': locked_task.task_id,
                    'job_task_id': locked_task.id,
                    'task_order': locked_task.task_order
                }
            )
            db.session.add(activity)
            
            db.session.commit()
            return True, "Task claimed successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to claim task: {str(e)}"

    def release_by_user(self, user_id):
        """Release a claimed task back to pending status"""
        if self.assigned_to_id != user_id or self.status not in ['claimed', 'blocked']:
            return False, "Task cannot be released by this user"
            
        try:
            self.status = 'pending'
            self.assigned_to_id = None
            self.claimed_at = None
            self.lock_version += 1
            
            # Log the release activity
            from models import ActivityLog
            activity = ActivityLog(
                job_id=self.job_id,
                user_id=user_id,
                event_type='task_released',
                payload={
                    'task_id': self.task_id,
                    'job_task_id': self.id,
                    'task_order': self.task_order
                }
            )
            db.session.add(activity)
            
            db.session.commit()
            return True, "Task released successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to release task: {str(e)}"

    def __repr__(self):
        return f'<JobTask {self.job_id}-{self.task_order} ({self.status})>'


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
    
    __table_args__ = (
        Index('idx_timer_task_user', 'job_task_id', 'user_id'),
    )

    @property
    def is_running(self):
        return self.stopped_at is None

    def stop(self):
        """Stop the timer and calculate duration"""
        if self.stopped_at is None:
            self.stopped_at = datetime.now(timezone.utc)
            self.duration_seconds = int((self.stopped_at - self.started_at).total_seconds())

    def __repr__(self):
        return f'<Timer {self.job_task_id} by {self.user_id}>'


class Photo(db.Model):
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    job_task_id = db.Column(db.Integer, db.ForeignKey('job_tasks.id'), nullable=True, index=True)
    type = db.Column(db.String(20), nullable=False)  # 'before', 'after', 'exception'
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    description = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        Index('idx_photo_job_type', 'job_id', 'type'),
        Index('idx_photo_task_type', 'job_task_id', 'type'),
    )

    @validates('type')
    def validate_type(self, key, photo_type):
        if photo_type not in ['before', 'after', 'exception']:
            raise ValueError("Photo type must be 'before', 'after', or 'exception'")
        return photo_type

    def __repr__(self):
        return f'<Photo {self.filename} ({self.type})>'


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # 'task_claimed', 'task_completed', 'timer_started', etc.
    payload = db.Column(db.JSON, nullable=True)  # Event-specific data
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user = db.relationship('User', backref='activities')
    
    __table_args__ = (
        Index('idx_activity_job_time', 'job_id', 'timestamp'),
        Index('idx_activity_type_time', 'event_type', 'timestamp'),
    )

    def __repr__(self):
        return f'<ActivityLog {self.event_type} by {self.user_id}>'