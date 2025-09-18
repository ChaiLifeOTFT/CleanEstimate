import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from werkzeug.utils import secure_filename
import uuid
import json
import sys
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import qrcode
from io import BytesIO
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the database with the app
db.init_app(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Configure CSRF Protection
csrf = CSRFProtect(app)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def role_required(required_role):
    """Decorator to require specific user role"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role != required_role:
                flash(f'Access denied. This feature requires {required_role} role.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize database and create tables
with app.app_context():
    # Import all models here so they're registered with SQLAlchemy
    import models
    db.create_all()

# Session configuration for better persistence
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=24)

# Production-ready session security settings
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # True for HTTPS in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # Flask-Login remember me security

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Task library with comprehensive cleaning guidance including products, methods, and safety
task_library = {
    "Rough Clean": [
        {
            "task": "Clean all tubs and shower pans",
            "time_per_100": 1.2,
            "instructions": "Clean all tubs and shower pans thoroughly. Remove construction debris, adhesive residue, and protective films.",
            "method": "Spray Zep Calcium, Lime & Rust Remover on all surfaces. Let sit 2-3 minutes. Scrub with non-abrasive pad in circular motions. Rinse thoroughly with clean water and dry with microfiber cloth.",
            "materials": ["Zep Calcium, Lime & Rust Remover", "Non-abrasive scrub pad", "Microfiber cloths", "Clean water", "Rubber gloves"],
            "approved_products": ["✅ Zep Calcium, Lime & Rust Remover", "🔄 CLR (backup)", "🔄 Barkeepers Friend (for stubborn stains)"],
            "precautions": "Never use steel wool or abrasive cleaners on acrylic or fiberglass surfaces. Test on inconspicuous area first. Ensure adequate ventilation."
        },
        {
            "task": "Clean window frames inside and outside",
            "time_per_100": 1.5,
            "instructions": "Clean all window frames both inside and outside, removing construction dust, paint splatters, and adhesive residue.",
            "method": "Spray Zep All-Purpose Cleaner on frames. Use detail brush for crevices and corners. Wipe clean with microfiber cloth. For paint removal, use plastic scraper then re-clean.",
            "materials": ["Zep All-Purpose Cleaner", "Detail brush", "Microfiber cloths", "Plastic scraper", "Extension pole (if needed)"],
            "approved_products": ["✅ Zep All-Purpose Cleaner", "🔄 Simple Green (backup)", "🔄 Goof Off (for adhesive removal)"],
            "precautions": "Do not use metal scrapers on frames. Be careful around weatherstripping and seals. Avoid getting cleaner on glass surfaces."
        },
        {
            "task": "Clean sliding glass door frames and panels",
            "time_per_100": 1.0,
            "instructions": "Clean sliding glass door frames and glass panels. Ensure smooth operation and streak-free glass.",
            "method": "Remove loose debris from tracks. Spray Zep Foaming Glass Cleaner on glass panels. Clean frames with All-Purpose Cleaner. Buff glass with lint-free cloth in circular motions.",
            "materials": ["Zep Foaming Glass Cleaner", "Zep All-Purpose Cleaner", "Lint-free cloths", "Detail brush", "Vacuum with brush attachment"],
            "approved_products": ["✅ Zep Foaming Glass Cleaner", "✅ Zep All-Purpose Cleaner", "🔄 Sprayway Glass Cleaner (backup)"],
            "precautions": "Do not spray cleaner directly into tracks. Ensure doors slide smoothly after cleaning. Check for loose glass panels."
        },
        {
            "task": "Clean and vacuum window and door tracks",
            "time_per_100": 0.8,
            "instructions": "Remove all construction debris, dust, and materials from window and door tracks. Ensure smooth operation.",
            "method": "Vacuum tracks with brush attachment. Use detail brush to remove stubborn debris. Spray tracks with compressed air if available. Wipe with damp microfiber cloth.",
            "materials": ["Vacuum with brush attachment", "Detail brush", "Microfiber cloths", "Compressed air (optional)", "Small screwdriver for debris removal"],
            "approved_products": ["✅ Zep All-Purpose Cleaner (for stubborn residue)", "🔄 Simple Green (backup)"],
            "precautions": "Do not force debris removal that might damage tracks. Check for proper window/door operation after cleaning."
        },
        {
            "task": "Clean cabinets and vanities inside and outside",
            "time_per_100": 2.0,
            "instructions": "Clean all cabinet exteriors, interiors, doors, and tops. Remove construction dust, fingerprints, and protective films.",
            "method": "Vacuum cabinet interiors first. Spray Zep Wood Floor & Cabinet Cleaner on cloth (not directly on surface). Wipe in direction of wood grain. Clean hardware with All-Purpose Cleaner on cloth.",
            "materials": ["Zep Wood Floor & Cabinet Cleaner", "Zep All-Purpose Cleaner", "Microfiber cloths", "Vacuum with brush attachment", "Step ladder"],
            "approved_products": ["✅ Zep Wood Floor & Cabinet Cleaner", "✅ Zep All-Purpose Cleaner", "🔄 Murphy's Oil Soap (backup)", "🔄 Method Wood Cleaner (backup)"],
            "precautions": "Never spray cleaner directly on wood surfaces. Test on inconspicuous area first. Do not oversaturate wood. Clean spills immediately."
        },
        {
            "task": "Clean all drawers",
            "time_per_100": 0.6,
            "instructions": "Vacuum and wipe clean all drawer interiors and exteriors. Remove construction debris and dust.",
            "method": "Remove drawers if possible. Vacuum interiors thoroughly. Wipe with damp microfiber cloth using Wood Floor & Cabinet Cleaner. Check drawer slides and clean if needed.",
            "materials": ["Zep Wood Floor & Cabinet Cleaner", "Microfiber cloths", "Vacuum with brush attachment", "Detail brush"],
            "approved_products": ["✅ Zep Wood Floor & Cabinet Cleaner", "🔄 Method Wood Cleaner (backup)"],
            "precautions": "Handle drawers carefully to avoid damage to slides. Do not force stuck drawers. Check weight limits."
        },
        {
            "task": "Clean closet shelves",
            "time_per_100": 0.4,
            "instructions": "Remove dust and construction debris from all closet shelf surfaces, brackets, and support systems.",
            "method": "Dust shelves with microfiber cloth first. Spray Wood Floor & Cabinet Cleaner on cloth and wipe shelves. Clean brackets and supports with All-Purpose Cleaner.",
            "materials": ["Zep Wood Floor & Cabinet Cleaner", "Zep All-Purpose Cleaner", "Microfiber cloths", "Step ladder"],
            "approved_products": ["✅ Zep Wood Floor & Cabinet Cleaner", "✅ Zep All-Purpose Cleaner", "🔄 Pledge (backup)"],
            "precautions": "Check shelf stability before applying weight. Clean support brackets to ensure proper function."
        },
        {
            "task": "Clean interior and exterior doors",
            "time_per_100": 1.0,
            "instructions": "Clean all door surfaces, hardware, and thresholds. Remove paint overspray, fingerprints, and adhesive residue.",
            "method": "For painted doors: use All-Purpose Cleaner on microfiber cloth. For wood doors: use Wood Floor & Cabinet Cleaner. Clean hardware with All-Purpose Cleaner. Use plastic scraper for paint removal.",
            "materials": ["Zep All-Purpose Cleaner", "Zep Wood Floor & Cabinet Cleaner", "Microfiber cloths", "Plastic scraper", "Detail brush"],
            "approved_products": ["✅ Zep All-Purpose Cleaner", "✅ Zep Wood Floor & Cabinet Cleaner", "🔄 Goof Off (for stubborn residue)"],
            "precautions": "Test cleaners on inconspicuous area. Do not use abrasive materials on hardware. Check door operation after cleaning."
        },
        {
            "task": "Clean electrical fixtures and appliances",
            "time_per_100": 1.2,
            "instructions": "Clean all light fixtures, switch plates, outlet covers, and exposed appliances. Remove construction dust and fingerprints.",
            "method": "Turn off power to fixtures when possible. Use damp microfiber cloth with All-Purpose Cleaner. For glass fixtures, use Foaming Glass Cleaner. Dry thoroughly before restoring power.",
            "materials": ["Zep All-Purpose Cleaner", "Zep Foaming Glass Cleaner", "Microfiber cloths", "Step ladder", "Non-conductive cleaning tools"],
            "approved_products": ["✅ Zep All-Purpose Cleaner", "✅ Zep Foaming Glass Cleaner", "🔄 Simple Green (backup)"],
            "precautions": "Turn off power before cleaning. Never spray cleaner directly on electrical components. Ensure hands and materials are dry. Use non-metal tools near electrical."
        },
        {
            "task": "Clean plumbing fixtures",
            "time_per_100": 1.5,
            "instructions": "Clean all sinks, faucets, toilets, and plumbing hardware. Remove water spots, construction dust, and protective films.",
            "method": "Use Calcium, Lime & Rust Remover for mineral deposits. Scrub gently with non-abrasive pad. For chrome fixtures, use Foaming Glass Cleaner for streak-free finish. Dry with microfiber cloth.",
            "materials": ["Zep Calcium, Lime & Rust Remover", "Zep Foaming Glass Cleaner", "Non-abrasive scrub pads", "Microfiber cloths", "Toilet brush"],
            "approved_products": ["✅ Zep Calcium, Lime & Rust Remover", "✅ Zep Foaming Glass Cleaner", "🔄 CLR (backup)", "🔄 Barkeepers Friend (for stubborn stains)"],
            "precautions": "Do not mix different cleaners. Test on inconspicuous area first. Avoid abrasive materials on chrome or brushed finishes. Ensure adequate ventilation."
        }
    ],
    "Final Clean": [
        {
            "task": "Final polish of all surfaces",
            "time_per_100": 1.5,
            "instructions": "Perform final detailing and polishing of all surfaces. Ensure showroom-quality finish for homeowner delivery.",
            "method": "Dust all surfaces first. Apply appropriate Zep cleaner based on surface type. Buff to shine with clean microfiber cloths. Check for missed spots under different lighting.",
            "materials": ["Zep Wood Floor & Cabinet Cleaner", "Zep All-Purpose Cleaner", "Zep Foaming Glass Cleaner", "Multiple microfiber cloths", "Dusting spray"],
            "approved_products": ["✅ Zep Complete Product Line", "🔄 Pledge (for wood)", "🔄 Windex (for glass)"],
            "precautions": "Use appropriate cleaner for each surface type. Work in good lighting to spot imperfections. Allow surfaces to dry completely."
        },
        {
            "task": "Final window and glass cleaning",
            "time_per_100": 1.0,
            "instructions": "Achieve streak-free, crystal-clear finish on all windows and glass surfaces for final inspection.",
            "method": "Spray Zep Foaming Glass Cleaner on glass. Use squeegee for large surfaces, microfiber for small areas. Buff edges and corners with lint-free cloth. Check for streaks in different lighting.",
            "materials": ["Zep Foaming Glass Cleaner", "Professional squeegee", "Lint-free cloths", "Extension pole", "Razor blade for stubborn spots"],
            "approved_products": ["✅ Zep Foaming Glass Cleaner", "🔄 Sprayway Glass Cleaner", "🔄 Invisible Glass (backup)"],
            "precautions": "Work in shade when possible. Clean glass when cool to touch. Use proper ladder safety for high windows."
        },
        {
            "task": "Final floor cleaning and inspection",
            "time_per_100": 2.0,
            "instructions": "Complete final cleaning of all flooring surfaces. Vacuum carpets, clean hard surfaces, and perform quality inspection.",
            "method": "Vacuum carpets with crevice tool along edges. Mop hard floors with Zep Neutral Floor Cleaner. Check for missed debris, spots, or damage. Touch up as needed.",
            "materials": ["Zep Neutral Floor Cleaner", "Professional vacuum", "Microfiber mop", "Clean mop water", "Spot cleaning supplies"],
            "approved_products": ["✅ Zep Neutral Floor Cleaner", "✅ Zep Wood Floor & Cabinet Cleaner (for wood)", "🔄 Bona (for hardwood backup)"],
            "precautions": "Use appropriate cleaner for floor type. Change mop water frequently. Check for proper drying to avoid water damage."
        }
    ],
    "QC Clean": [
        {
            "task": "Quality control inspection and touch-ups",
            "time_per_100": 1.0,
            "instructions": "Conduct comprehensive quality inspection using checklist. Address any deficiencies found during inspection.",
            "method": "Systematically inspect each room with QC checklist. Use flashlight to check corners and hidden areas. Touch up any missed spots with appropriate Zep products. Document any issues.",
            "materials": ["QC inspection checklist", "Flashlight", "Full range of Zep cleaners", "Microfiber cloths", "Touch-up supplies"],
            "approved_products": ["✅ Complete Zep Product Line", "🔄 Spot-specific alternatives as needed"],
            "precautions": "Be thorough but efficient. Document any damage or pre-existing conditions. Ensure all team members understand QC standards."
        },
        {
            "task": "Final quality verification",
            "time_per_100": 0.5,
            "instructions": "Final walkthrough to verify all ResiBuilt quality standards are met before homeowner delivery.",
            "method": "Complete final walkthrough with supervisor or lead cleaner. Verify all checklist items are complete. Take final photos if required. Ensure all supplies are removed.",
            "materials": ["Final inspection checklist", "Camera for documentation", "Any final touch-up supplies"],
            "approved_products": ["✅ Any remaining Zep products for final touch-ups"],
            "precautions": "Double-check all areas are accessible to homeowner. Ensure no cleaning supplies or equipment left behind. Verify all utilities are functioning."
        }
    ],
    "Spec Clean": [
        {
            "task": "Specification-based cleaning tasks",
            "time_per_100": 1.2,
            "instructions": "Complete any specific cleaning tasks as outlined in the project specifications. Address special requirements or custom needs.",
            "method": "Review project specifications carefully. Use appropriate Zep products based on surface types and requirements. Follow any special procedures outlined in the specs.",
            "materials": ["Project specifications", "Full range of Zep cleaners", "Specialized tools as required", "Safety equipment"],
            "approved_products": ["✅ Zep products appropriate for specified surfaces", "🔄 Specialty products as approved by supervisor"],
            "precautions": "Follow all safety requirements in specifications. Get supervisor approval for any deviations. Document any special procedures used."
        },
        {
            "task": "Special attention areas",
            "time_per_100": 0.8,
            "instructions": "Focus on areas requiring special attention as specified in project requirements. Ensure all specification requirements are met.",
            "method": "Identify special attention areas from project documents. Apply extra care and appropriate products. Verify completion meets or exceeds specified standards.",
            "materials": ["Project documentation", "Appropriate Zep cleaners", "Specialized equipment", "Measuring tools if needed"],
            "approved_products": ["✅ Zep products suitable for special requirements", "🔄 Approved specialty products"],
            "precautions": "Pay extra attention to specified areas. Document completion with photos if required. Ensure compliance with all special requirements."
        }
    ]
}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save an uploaded file and return the filename."""
    if file and file.filename and allowed_file(file.filename):
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{file_extension}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

def generate_qr_code(url):
    """Generate QR code for a URL and return as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def calculate_task_times(cleaning_type, square_footage):
    """Calculate estimated time for each task based on square footage"""
    tasks = task_library.get(cleaning_type, [])
    calculated_tasks = []
    
    for task in tasks:
        # Calculate time based on square footage
        # Formula: (square_footage / 100) * time_per_100 + 5 minute buffer
        base_minutes = (square_footage / 100) * task["time_per_100"]
        estimated_minutes = base_minutes + 5  # Add 5 minute cleaning window buffer
        
        calculated_task = {
            "task": task["task"],
            "instructions": task["instructions"],
            "method": task["method"],
            "materials": task["materials"],
            "approved_products": task["approved_products"],
            "precautions": task["precautions"],
            "estimated_minutes": round(estimated_minutes, 1),
            "estimated_hours": round(estimated_minutes / 60, 2)
        }
        calculated_tasks.append(calculated_task)
    
    return calculated_tasks

@app.route('/')
def index():
    """Homepage with the job estimation form"""
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_job():
    """Handle legacy form submission and redirect to database-backed job creation"""
    app.logger.info("Legacy job submission received - redirecting to database-backed system")
    
    # For legacy compatibility, redirect users to create an account and use the new system
    if not current_user.is_authenticated:
        flash('Please create an account to use the new team-based job management system with real-time coordination.', 'info')
        return redirect(url_for('register'))
    
    # If user is authenticated but not a coordinator, show message about team-based system
    if current_user.role != 'coordinator':
        flash('Only coordinators can create jobs in the new team-based system. Please contact your coordinator.', 'info')
        return redirect(url_for('dashboard'))
    
    # If user is a coordinator, redirect them to create a job in the database system
    flash('Please use the new job creation system for better team coordination and task management.', 'info')
    return redirect(url_for('create_job'))

@app.route('/task/<int:job_id>/<int:task_order>')
@login_required
def task_page(job_id, task_order):
    """Individual task page with database-backed job data"""
    from models import Job, JobTask, JobTeamMember, Timer
    
    # Get the job
    job = Job.query.get_or_404(job_id)
    
    # Check if user has access to this job
    is_coordinator = (current_user.role == 'coordinator' and job.coordinator_id == current_user.id)
    is_team_member = JobTeamMember.query.filter_by(
        job_id=job_id, 
        user_id=current_user.id
    ).first() is not None
    
    if not (is_coordinator or is_team_member):
        flash('Access denied. You must be assigned to this job.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the specific task by order
    job_task = JobTask.query.filter_by(
        job_id=job_id, 
        task_order=task_order
    ).first_or_404()
    
    # Check if task is claimed by current user or available
    if current_user.role == 'cleaner' and job_task.status == 'pending':
        flash('Please claim this task first before starting work.', 'info')
        return redirect(url_for('job_tasks', job_id=job_id))
    elif current_user.role == 'cleaner' and job_task.assigned_to_id != current_user.id:
        flash('This task is assigned to another team member.', 'error')
        return redirect(url_for('job_tasks', job_id=job_id))
    
    # Get all job tasks for progress calculation
    total_tasks = JobTask.query.filter_by(job_id=job_id).count()
    completed_tasks = JobTask.query.filter_by(job_id=job_id, status='completed').count()
    
    progress = {
        'current': task_order + 1,
        'total': total_tasks,
        'percentage': round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    }
    
    # Get timer data for this task
    timer = Timer.query.filter_by(
        job_task_id=job_task.id,
        user_id=current_user.id,
        stopped_at=None
    ).first()
    
    # Convert timer to legacy format for template compatibility
    timer_data = None
    if timer:
        timer_data = {
            'start_time': timer.started_at.isoformat(),
            'status': 'running',
            'actual_minutes': 0
        }
    
    app.logger.info(f"Task page {task_order}: Job {job_id}, User {current_user.id}, Timer active: {timer is not None}")
    
    return render_template('task.html', 
                         task={
                             'task': job_task.task.name,
                             'instructions': job_task.task.instructions,
                             'method': job_task.task.method,
                             'materials': job_task.task.materials,
                             'approved_products': job_task.task.approved_products,
                             'precautions': job_task.task.precautions,
                             'estimated_minutes': job_task.estimated_minutes
                         },
                         task_index=task_order,
                         job_data={
                             'client_name': job.client_name,
                             'job_address': job.job_address,
                             'cleaning_type': job.cleaning_type,
                             'square_footage': job.square_footage
                         },
                         progress=progress,
                         timer_data=timer_data,
                         job=job,
                         job_task=job_task)

@app.route('/upload_before_photo', methods=['POST'])
def upload_before_photo():
    """Handle before photo upload when starting a task."""
    try:
        if 'before_photo' not in request.files:
            return jsonify({'error': 'No photo provided'}), 400
        
        photo = request.files['before_photo']
        if photo and photo.filename:
            filename = save_uploaded_file(photo)
            if filename:
                # Store the filename in session for later use
                task_index = request.form.get('task_index', 0)
                if 'task_photos' not in session:
                    session['task_photos'] = {}
                session['task_photos'][str(task_index)] = {'before': filename}
                session.modified = True
                
                return jsonify({'filename': filename, 'success': True})
            else:
                return jsonify({'error': 'Failed to save photo'}), 500
        
        return jsonify({'error': 'Invalid photo'}), 400
    except Exception as e:
        app.logger.error(f"Error uploading before photo: {str(e)}")
        return jsonify({'error': 'An error occurred'}), 500

@app.route('/complete_task/<int:task_index>', methods=['POST'])
def complete_task(task_index):
    """Handle task completion with after photo"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    try:
        job_data = session['job_data']
        tasks = job_data['tasks']
        
        if task_index >= len(tasks):
            return redirect(url_for('job_complete'))
        
        current_task = tasks[task_index]
        
        # Get the before photo filename from session or form (already uploaded)
        before_photo_filename = None
        if 'task_photos' in session and str(task_index) in session['task_photos']:
            before_photo_filename = session['task_photos'][str(task_index)].get('before')
        elif 'before_photo_filename' in request.form:
            before_photo_filename = request.form['before_photo_filename']
        
        # Handle after photo upload (required)
        after_photo_filename = None
        if 'task_after_photo' in request.files:
            after_file = request.files['task_after_photo']
            if after_file and after_file.filename:
                after_photo_filename = save_uploaded_file(after_file)
                if not after_photo_filename:
                    flash('Failed to save after photo. Please try again.', 'error')
                    return redirect(url_for('task_page', task_index=task_index))
        
        # Get timer data if exists
        timer_data = job_data.get('task_timers', {}).get(str(task_index), {})
        actual_minutes = timer_data.get('actual_minutes', current_task['estimated_minutes'])
        time_extensions = timer_data.get('time_extensions', [])
        
        # Store task completion data
        completed_task = {
            'task_index': task_index,
            'task_name': current_task['task'],
            'estimated_minutes': current_task['estimated_minutes'],
            'actual_minutes': actual_minutes,
            'time_extensions': time_extensions,
            'before_photo': before_photo_filename,
            'after_photo': after_photo_filename,
            'completed_at': str(uuid.uuid4())  # Simple timestamp placeholder
        }
        
        job_data['completed_tasks'].append(completed_task)
        job_data['current_task_index'] = task_index + 1
        session['job_data'] = job_data
        
        # Move to next task
        next_task_index = task_index + 1
        if next_task_index >= len(tasks):
            return redirect(url_for('job_complete'))
        else:
            return redirect(url_for('task_page', task_index=next_task_index))
            
    except Exception as e:
        app.logger.error(f"Error completing task: {str(e)}")
        flash('An error occurred while completing the task. Please try again.', 'error')
        return redirect(url_for('task_page', task_index=task_index))

@app.route('/start_task/<int:job_id>/<int:task_order>', methods=['POST'])
@login_required
def start_task(job_id, task_order):
    """Start database-backed timer for a specific task"""
    from models import JobTask, Timer
    
    try:
        # Get the job task
        job_task = JobTask.query.filter_by(
            job_id=job_id,
            task_order=task_order
        ).first_or_404()
        
        # Check if user has permission to start this task
        if job_task.assigned_to_id != current_user.id:
            return jsonify({'error': 'Task not assigned to you'}), 403
        
        if job_task.status not in ['claimed', 'in_progress']:
            return jsonify({'error': 'Task must be claimed before starting timer'}), 400
        
        # Check if timer is already running
        existing_timer = Timer.query.filter_by(
            job_task_id=job_task.id,
            user_id=current_user.id,
            stopped_at=None
        ).first()
        
        if existing_timer:
            return jsonify({'error': 'Timer is already running for this task'}), 400
        
        # Create new timer
        timer = Timer(
            job_task_id=job_task.id,
            user_id=current_user.id,
            started_at=datetime.now(timezone.utc)
        )
        db.session.add(timer)
        
        # Update task status to in_progress
        job_task.status = 'in_progress'
        job_task.started_at = datetime.now(timezone.utc)
        
        # Log activity
        from models import ActivityLog
        activity = ActivityLog(
            job_id=job_task.job_id,
            user_id=current_user.id,
            event_type='timer_started',
            payload={
                'task_id': job_task.task_id,
                'job_task_id': job_task.id,
                'task_order': job_task.task_order
            }
        )
        db.session.add(activity)
        
        db.session.commit()
        
        app.logger.info(f"Timer started for task {task_order} in job {job_id} by user {current_user.id}")
        return jsonify({
            'success': True, 
            'start_time': timer.started_at.isoformat(),
            'timer_id': timer.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error starting task timer {task_order}: {str(e)}")
        return jsonify({'error': f'Failed to start timer: {str(e)}'}), 500

@app.route('/request_more_time/<int:task_index>', methods=['POST'])
def request_more_time(task_index):
    """Request more time for a task"""
    if 'job_data' not in session:
        app.logger.error(f"Request extension task {task_index}: No job data in session")
        return jsonify({'error': 'No active job found'}), 400
    
    try:
        from datetime import datetime
        job_data = session['job_data']
        app.logger.info(f"Request extension task {task_index}: Found job data for {job_data.get('client_name', 'Unknown')}")
        
        # Safely get JSON data
        json_data = request.get_json()
        if json_data is None:
            app.logger.error(f"Request extension task {task_index}: Invalid JSON data")
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        reason = json_data.get('reason', 'Additional time needed')
        additional_minutes = json_data.get('additional_minutes', 5)
        
        app.logger.info(f"Request extension task {task_index}: Available timers: {list(job_data.get('task_timers', {}).keys())}")
        
        if str(task_index) in job_data.get('task_timers', {}):
            extension = {
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'additional_minutes': additional_minutes
            }
            job_data['task_timers'][str(task_index)]['time_extensions'].append(extension)
            session['job_data'] = job_data
            session.modified = True
            
            app.logger.info(f"Request extension task {task_index}: Extension granted: +{additional_minutes} min")
            return jsonify({'success': True, 'extension': extension}), 200
        else:
            app.logger.error(f"Request extension task {task_index}: Timer not found")
            return jsonify({'error': 'Task timer not started'}), 400
            
    except Exception as e:
        app.logger.error(f"Error requesting more time for task {task_index}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/stop_task/<int:job_id>/<int:task_order>', methods=['POST'])
@login_required  
def stop_task(job_id, task_order):
    """Stop database-backed timer for a specific task"""
    from models import JobTask, Timer
    
    try:
        # Get the job task
        job_task = JobTask.query.filter_by(
            job_id=job_id,
            task_order=task_order
        ).first_or_404()
        
        # Check if user has permission to stop this task
        if job_task.assigned_to_id != current_user.id:
            return jsonify({'error': 'Task not assigned to you'}), 403
        
        # Find the running timer
        timer = Timer.query.filter_by(
            job_task_id=job_task.id,
            user_id=current_user.id,
            stopped_at=None
        ).first()
        
        if not timer:
            return jsonify({'error': 'No running timer found for this task'}), 400
        
        # Stop the timer
        timer.stop()
        
        # Update job task with timer total
        job_task.timer_total_seconds += timer.duration_seconds
        
        # Check if task should be marked completed
        # (This could be expanded with completion criteria)
        if job_task.status == 'in_progress':
            # For now, stopping timer keeps task in progress
            # Task completion would be handled by a separate endpoint
            pass
        
        # Log activity
        from models import ActivityLog
        activity = ActivityLog(
            job_id=job_task.job_id,
            user_id=current_user.id,
            event_type='timer_stopped',
            payload={
                'task_id': job_task.task_id,
                'job_task_id': job_task.id,
                'task_order': job_task.task_order,
                'duration_seconds': timer.duration_seconds,
                'duration_minutes': round(timer.duration_seconds / 60, 1)
            }
        )
        db.session.add(activity)
        
        db.session.commit()
        
        actual_minutes = round(timer.duration_seconds / 60, 1)
        app.logger.info(f"Timer stopped for task {task_order} in job {job_id}, duration: {actual_minutes} minutes")
        
        return jsonify({
            'success': True, 
            'actual_minutes': actual_minutes,
            'timer_id': timer.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error stopping task timer {task_order}: {str(e)}")
        return jsonify({'error': f'Failed to stop timer: {str(e)}'}), 500

@app.route('/add_exception/<int:task_index>', methods=['POST'])
def add_exception(task_index):
    """Add an exception/issue for a specific task"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    try:
        job_data = session['job_data']
        tasks = job_data['tasks']
        
        if task_index >= len(tasks):
            flash('Invalid task index.', 'error')
            return redirect(url_for('job_complete'))
        
        # Get exception data from form
        issue_type = request.form.get('issue_type', '').strip()
        description = request.form.get('description', '').strip()
        recommended_action = request.form.get('recommended_action', '').strip()
        notified_client = request.form.get('notified_client') == 'yes'
        cleaner_initials = request.form.get('cleaner_initials', '').strip()
        
        if not all([issue_type, description]):
            flash('Issue type and description are required.', 'error')
            return redirect(url_for('task_page', task_index=task_index))
        
        # Handle exception photo upload
        exception_photo_filename = None
        if 'exception_photo' in request.files:
            exception_file = request.files['exception_photo']
            if exception_file and exception_file.filename and allowed_file(exception_file.filename):
                file_extension = exception_file.filename.rsplit('.', 1)[1].lower()
                exception_photo_filename = f"exception_{task_index}_{uuid.uuid4()}.{file_extension}"
                exception_file.save(os.path.join(app.config['UPLOAD_FOLDER'], exception_photo_filename))
        
        # Create exception record
        from datetime import datetime
        exception_record = {
            'task_index': task_index,
            'task_name': tasks[task_index]['task'],
            'issue_type': issue_type,
            'description': description,
            'recommended_action': recommended_action,
            'notified_client': notified_client,
            'cleaner_initials': cleaner_initials,
            'exception_photo': exception_photo_filename,
            'timestamp': datetime.now().strftime('%Y-%m-%d %I:%M%p'),
            'exception_id': str(uuid.uuid4())
        }
        
        # Add to exceptions list
        job_data['exceptions'].append(exception_record)
        session['job_data'] = job_data
        
        flash('Exception documented successfully.', 'success')
        return redirect(url_for('task_page', task_index=task_index))
        
    except Exception as e:
        app.logger.error(f"Error adding exception: {str(e)}")
        flash('An error occurred while documenting the exception. Please try again.', 'error')
        return redirect(url_for('task_page', task_index=task_index))

@app.route('/send_report', methods=['POST'])
def send_report():
    """Send job completion report via email"""
    if 'job_data' not in session:
        return jsonify({'error': 'No active job found'}), 400
    
    try:
        job_data = session['job_data']
        additional_email = request.json.get('additional_email', '').strip()
        
        # Get SendGrid API key
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_key:
            return jsonify({'error': 'Email service not configured'}), 500
        
        # Build email content
        subject = f"🧼 Job Completed - {job_data['cleaning_type']} at {job_data['job_address']}"
        
        # Calculate actual vs estimated time
        total_actual_minutes = sum(task.get('actual_minutes', task['estimated_minutes']) 
                                  for task in job_data.get('completed_tasks', []))
        actual_hours = round(total_actual_minutes / 60, 2)
        
        # Build HTML email body
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #2c5530;">🧼 Job Completed - Drake's Precision Cleaning</h2>
            
            <h3>Job Details:</h3>
            <ul>
                <li><strong>Client:</strong> {job_data['client_name']}</li>
                <li><strong>Cleaner:</strong> {job_data['cleaner_name']}</li>
                <li><strong>Location:</strong> {job_data['job_address']}</li>
                {'<li><strong>Lot Number:</strong> ' + job_data.get('lot_number', '') + '</li>' if job_data.get('lot_number') else ''}
                <li><strong>Type:</strong> {job_data['cleaning_type']}</li>
                <li><strong>Square Footage:</strong> {job_data['square_footage']:,} sq ft</li>
                <li><strong>Estimated Time:</strong> {job_data['total_estimated_hours']} hours</li>
                <li><strong>Actual Time:</strong> {actual_hours} hours</li>
            </ul>
            
            <h3>Tasks Completed:</h3>
            <ul>
        """
        
        # Add task details
        for task in job_data.get('completed_tasks', []):
            actual_min = task.get('actual_minutes', task['estimated_minutes'])
            status = "✅" if actual_min <= task['estimated_minutes'] else "⚠️"
            html_content += f"<li>{status} <strong>{task['task_name']}:</strong> {actual_min:.1f} min (est: {task['estimated_minutes']} min)</li>"
        
        html_content += "</ul>"
        
        # Add exceptions if any
        if job_data.get('exceptions'):
            html_content += "<h3>⚠️ Exceptions & Issues:</h3><ul>"
            for exc in job_data['exceptions']:
                html_content += f"""
                <li>
                    <strong>{exc['issue_type']}</strong><br>
                    {exc['description']}<br>
                    <em>Action: {exc.get('recommended_action', 'None specified')}</em><br>
                    <small>Reported by: {exc.get('cleaner_initials', 'Unknown')} | Client notified: {'Yes' if exc.get('notified_client') else 'No'}</small>
                </li>
                """
            html_content += "</ul>"
        
        html_content += """
            <hr>
            <p style="color: #666; font-size: 12px;">
                This report was generated automatically by Drake's Precision Cleaning App.<br>
                For questions, please contact drakesprecisioncleaning@gmail.com
            </p>
        </body>
        </html>
        """
        
        # Create SendGrid message
        sg = SendGridAPIClient(sendgrid_key)
        
        # Always send to company email
        to_emails = [To('drakesprecisioncleaning@gmail.com')]
        
        # Add additional recipient if provided
        if additional_email and '@' in additional_email:
            to_emails.append(To(additional_email))
        
        message = Mail(
            from_email=Email('noreply@drakesprecisionclean.com', 'Drake\'s Precision Cleaning'),
            to_emails=to_emails,
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        # Send email
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            recipients = 'drakesprecisioncleaning@gmail.com'
            if additional_email:
                recipients += f' and {additional_email}'
            return jsonify({
                'success': True, 
                'message': f'Report sent successfully to {recipients}'
            }), 200
        else:
            return jsonify({'error': 'Failed to send email'}), 500
            
    except Exception as e:
        app.logger.error(f"Error sending report: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/job_complete')
def job_complete():
    """Job completion summary page"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    job_data = session['job_data']
    
    # Generate unique job ID if not exists
    if 'job_id' not in job_data:
        job_data['job_id'] = str(uuid.uuid4())[:8]
        session['job_data'] = job_data
    
    # Generate QR code for the report URL
    report_url = request.url_root + f"report/{job_data['job_id']}"
    job_data['qr_code'] = generate_qr_code(report_url)
    job_data['report_url'] = report_url
    
    return render_template('job_complete.html', job_data=job_data)

@app.route('/performance')
def performance():
    """Performance analytics dashboard"""
    from datetime import datetime, timedelta
    import random  # For demo data
    
    # Get period from query params
    period = request.args.get('period', 'month')
    
    # Set period label
    if period == 'week':
        period_label = 'Last 7 Days'
    elif period == 'month':
        period_label = 'Last 30 Days'
    else:
        period_label = 'All Time'
    
    # Demo performance metrics (in production, this would come from database)
    metrics = {
        'total_jobs': 47 if period == 'month' else 12 if period == 'week' else 156,
        'avg_completion_time': 185,
        'efficiency_rate': 92,
        'total_sqft': 145000 if period == 'month' else 38000 if period == 'week' else 485000
    }
    
    # Cleaner statistics
    cleaner_stats = [
        {
            'name': 'Maria Rodriguez',
            'job_count': 18 if period == 'month' else 5 if period == 'week' else 62,
            'avg_time': 178,
            'efficiency': 95,
            'efficiency_class': 'good'
        },
        {
            'name': 'James Wilson',
            'job_count': 15 if period == 'month' else 4 if period == 'week' else 48,
            'avg_time': 192,
            'efficiency': 88,
            'efficiency_class': 'good'
        },
        {
            'name': 'Sarah Chen',
            'job_count': 14 if period == 'month' else 3 if period == 'week' else 46,
            'avg_time': 185,
            'efficiency': 92,
            'efficiency_class': 'good'
        }
    ]
    
    # Task performance data for charts
    task_labels = ['Kitchen', 'Bathrooms', 'Living Areas', 'Bedrooms', 'Windows', 'Floors']
    task_times = [45, 35, 30, 25, 20, 40]
    
    # Job type comparison
    job_types = ['Move-in Ready', 'Final Clean', 'Rough Clean']
    estimated_times = [180, 240, 300]
    actual_times = [175, 252, 290]
    
    # Time distribution
    time_distribution = [65, 20, 15]  # On time, Overtime, Under time
    
    # Task breakdown with performance metrics
    task_breakdown = [
        {
            'name': 'Kitchen - All Surfaces',
            'count': 47 if period == 'month' else 12 if period == 'week' else 156,
            'avg_estimated': 45,
            'avg_actual': 43,
            'variance': -2,
            'performance': 95
        },
        {
            'name': 'Bathrooms - Complete',
            'count': 94 if period == 'month' else 24 if period == 'week' else 312,
            'avg_estimated': 35,
            'avg_actual': 38,
            'variance': 3,
            'performance': 88
        },
        {
            'name': 'Windows - Interior & Exterior',
            'count': 47 if period == 'month' else 12 if period == 'week' else 156,
            'avg_estimated': 20,
            'avg_actual': 18,
            'variance': -2,
            'performance': 98
        },
        {
            'name': 'Floors - Vacuum & Mop',
            'count': 47 if period == 'month' else 12 if period == 'week' else 156,
            'avg_estimated': 40,
            'avg_actual': 42,
            'variance': 2,
            'performance': 90
        },
        {
            'name': 'Bedrooms - All Areas',
            'count': 141 if period == 'month' else 36 if period == 'week' else 468,
            'avg_estimated': 25,
            'avg_actual': 24,
            'variance': -1,
            'performance': 96
        },
        {
            'name': 'Living Areas - Complete',
            'count': 47 if period == 'month' else 12 if period == 'week' else 156,
            'avg_estimated': 30,
            'avg_actual': 32,
            'variance': 2,
            'performance': 89
        }
    ]
    
    return render_template('performance.html',
                         period=period,
                         period_label=period_label,
                         metrics=metrics,
                         cleaner_stats=cleaner_stats,
                         task_labels=task_labels,
                         task_times=task_times,
                         job_types=job_types,
                         estimated_times=estimated_times,
                         actual_times=actual_times,
                         time_distribution=time_distribution,
                         task_breakdown=task_breakdown)

@app.route('/report/<job_id>')
def view_report(job_id):
    """View a job report by ID"""
    # In production, this would fetch from database
    # For now, check if it's the current session's job
    if 'job_data' in session and session.get('job_data', {}).get('job_id') == job_id:
        job_data = session['job_data']
        return render_template('job_complete.html', job_data=job_data, public_view=True)
    else:
        flash('Report not found or has expired.', 'error')
        return redirect(url_for('index'))

@app.route('/download_pdf/<job_id>')
def download_pdf(job_id):
    """Generate and download PDF report"""
    if 'job_data' not in session or session.get('job_data', {}).get('job_id') != job_id:
        flash('Report not found.', 'error')
        return redirect(url_for('index'))
    
    job_data = session['job_data']
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=12
    )
    
    # Title
    elements.append(Paragraph("Drake's Precision Cleaning", title_style))
    elements.append(Paragraph("Job Completion Report", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Job Information
    elements.append(Paragraph("Job Information", heading_style))
    
    job_info_data = [
        ['Client Name:', job_data.get('client_name', 'N/A')],
        ['Cleaner Name:', job_data.get('cleaner_name', 'N/A')],
        ['Job Address:', job_data.get('job_address', 'N/A')],
        ['Lot Number:', job_data.get('lot_number', 'N/A') if job_data.get('lot_number') else 'N/A'],
        ['Square Footage:', f"{job_data.get('square_footage', 0):,} sq ft"],
        ['Cleaning Type:', job_data.get('cleaning_type', 'N/A')],
        ['Total Est. Time:', f"{job_data.get('total_estimated_hours', 0)} hours ({job_data.get('total_estimated_minutes', 0)} minutes)"]
    ]
    
    job_table = Table(job_info_data, colWidths=[2*inch, 4*inch])
    job_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(job_table)
    elements.append(Spacer(1, 20))
    
    # Completed Tasks
    elements.append(Paragraph("Completed Tasks", heading_style))
    
    if job_data.get('completed_tasks'):
        for i, task in enumerate(job_data['completed_tasks'], 1):
            task_text = f"<b>{i}. {task.get('task_name', 'Unknown Task')}</b>"
            if task.get('actual_minutes'):
                task_text += f" - Completed in {task.get('actual_minutes', 0):.0f} minutes"
            elements.append(Paragraph(task_text, styles['Normal']))
            
            if task.get('exceptions'):
                for exc in task['exceptions']:
                    exc_text = f"   • Exception: {exc.get('issue_type', '')} - {exc.get('description', '')}"
                    elements.append(Paragraph(exc_text, styles['Normal']))
            
            elements.append(Spacer(1, 6))
    
    elements.append(Spacer(1, 20))
    
    # Exceptions Summary
    all_exceptions = []
    for task in job_data.get('completed_tasks', []):
        for exc in task.get('exceptions', []):
            all_exceptions.append(exc)
    
    if all_exceptions:
        elements.append(Paragraph("Exceptions/Issues", heading_style))
        for exc in all_exceptions:
            exc_text = f"<b>{exc.get('issue_type', '')}</b>: {exc.get('description', '')}"
            if exc.get('recommended_action'):
                exc_text += f"<br/>Recommended Action: {exc.get('recommended_action', '')}"
            elements.append(Paragraph(exc_text, styles['Normal']))
            elements.append(Spacer(1, 6))
    
    # Footer
    elements.append(Spacer(1, 30))
    footer_text = f"Report generated on {job_data.get('completion_date', 'N/A')}<br/>"
    footer_text += "Drake's Precision Cleaning - Professional Construction Cleaning Services"
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    # Prepare response
    buffer.seek(0)
    filename = f"cleaning_report_{job_data.get('client_name', 'unknown').replace(' ', '_')}_{job_id}.pdf"
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@app.route('/ai_chat', methods=['POST'])
def ai_chat():
    """AI chat assistant endpoint"""
    try:
        import requests
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get current task context if available
        task_context = ""
        if 'job_data' in session:
            job_data = session['job_data']
            current_task = data.get('current_task', '')
            if current_task:
                task_context = f"Current cleaning task: {current_task}. "
            task_context += f"Cleaning type: {job_data.get('cleaning_type', 'General')}. "
            task_context += f"Building size: {job_data.get('square_footage', 'Unknown')} sq ft. "
        
        # Enhanced system prompt for cleaning expertise
        system_prompt = f"""You are Drake's Precision Cleaning AI Assistant - an expert cleaning consultant for post-construction residential cleaning. 

{task_context}

You help professional cleaners with:
- Product recommendations (prefer Zep brand products)
- Stain removal techniques
- Surface-specific cleaning methods
- Safety precautions and procedures
- Time management tips
- Equipment troubleshooting

Always provide:
- Specific product names when possible
- Step-by-step instructions
- Safety warnings
- Estimated time requirements
- Alternative solutions if first method doesn't work

Keep responses concise but thorough. Focus on practical, actionable advice for professional cleaners working on construction sites."""

        # Make request to Perplexity API
        perplexity_url = "https://api.perplexity.ai/chat/completions"
        headers = {
            'Authorization': f'Bearer {os.environ.get("PERPLEXITY_API_KEY")}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 500,
            "temperature": 0.2,
            "top_p": 0.9,
            "stream": False
        }
        
        response = requests.post(perplexity_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            ai_response = response.json()
            assistant_message = ai_response['choices'][0]['message']['content']
            
            return jsonify({
                'success': True,
                'message': assistant_message,
                'citations': ai_response.get('citations', [])
            })
        else:
            app.logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
            return jsonify({'error': 'AI service temporarily unavailable'}), 500
            
    except Exception as e:
        app.logger.error(f"AI chat error: {str(e)}")
        return jsonify({'error': 'Unable to process request'}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if request.method == 'POST':
        from flask_login import login_user
        from werkzeug.security import check_password_hash
        from models import User
        
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Safe redirect - only allow relative URLs to prevent open redirect attacks
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and '//' not in next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        from werkzeug.security import generate_password_hash
        from models import User
        
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        # Force all new registrations to 'cleaner' role for security
        # Coordinators must be promoted by an admin
        role = 'cleaner'
        
        if not all([name, email, password]):
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')
        
        # Create new user
        try:
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    from flask_login import logout_user
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing available jobs and team coordination"""
    from models import Job, JobTeamMember
    
    # Get jobs where user is a team member
    user_jobs = db.session.query(Job).join(JobTeamMember).filter(
        JobTeamMember.user_id == current_user.id
    ).all()
    
    # Get jobs where user is coordinator
    coordinated_jobs = Job.query.filter_by(coordinator_id=current_user.id).all()
    
    return render_template('dashboard.html', 
                         user_jobs=user_jobs, 
                         coordinated_jobs=coordinated_jobs,
                         user=current_user)

@app.route('/create_job', methods=['GET', 'POST'])
@role_required('coordinator')
def create_job():
    """Create a new job - only coordinators can create jobs"""
    
    if request.method == 'POST':
        from models import Job, JobTeamMember, JobTask, Task
        
        # Get form data
        client_name = request.form.get('client_name', '').strip()
        job_address = request.form.get('job_address', '').strip()
        lot_number = request.form.get('lot_number', '').strip()
        square_footage = request.form.get('square_footage', type=int)
        cleaning_type = request.form.get('cleaning_type', '').strip()
        
        # Validate required fields
        if not all([client_name, job_address, square_footage, cleaning_type]):
            flash('All required fields must be filled.', 'error')
            return render_template('create_job.html')
        
        try:
            # Create the job
            new_job = Job(
                client_name=client_name,
                job_address=job_address,
                lot_number=lot_number,
                cleaning_type=cleaning_type,
                square_footage=square_footage,
                coordinator_id=current_user.id
            )
            db.session.add(new_job)
            db.session.flush()  # Get the job ID
            
            # Add coordinator to team
            team_member = JobTeamMember(
                job_id=new_job.id,
                user_id=current_user.id,
                role='coordinator'
            )
            db.session.add(team_member)
            
            # Get tasks for this cleaning type and create job tasks
            tasks = Task.query.filter_by(cleaning_type=cleaning_type).order_by(Task.id).all()
            total_estimated_minutes = 0
            
            for i, task in enumerate(tasks):
                # Calculate time based on square footage
                base_minutes = (square_footage / 100) * task.time_per_100_sqft
                estimated_minutes = base_minutes + 5  # Add 5 minute buffer
                total_estimated_minutes += estimated_minutes
                
                job_task = JobTask(
                    job_id=new_job.id,
                    task_id=task.id,
                    task_order=i,
                    estimated_minutes=round(estimated_minutes, 1)
                )
                db.session.add(job_task)
            
            new_job.total_estimated_minutes = round(total_estimated_minutes, 1)
            
            db.session.commit()
            flash(f'Job created successfully! {len(tasks)} tasks added.', 'success')
            return redirect(url_for('job_management', job_id=new_job.id))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Job creation error: {str(e)}")
            flash('Failed to create job. Please try again.', 'error')
    
    return render_template('create_job.html')


@app.route('/job/<int:job_id>/manage')
@role_required('coordinator')
def job_management(job_id):
    """Comprehensive job management dashboard for coordinators"""
    from models import Job, JobTask, JobTeamMember, User, ActivityLog, Timer
    
    job = Job.query.get_or_404(job_id)
    
    # Check if coordinator owns this job
    if job.coordinator_id != current_user.id:
        flash('Access denied. You must be the job coordinator.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all job tasks with their assigned users and progress
    job_tasks = db.session.query(JobTask).filter_by(job_id=job_id).order_by(JobTask.task_order).all()
    
    # Get team members with their user details - Fix: use proper join and select User objects
    team_members_query = db.session.query(JobTeamMember).join(User).filter(JobTeamMember.job_id == job_id).all()
    team_members = []
    for member in team_members_query:
        team_members.append(member)  # Now member.user will work due to relationship
    
    # Get recent activity for this job
    recent_activities = ActivityLog.query.filter_by(job_id=job_id).order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    # Calculate progress statistics
    total_tasks = len(job_tasks)
    completed_tasks = len([task for task in job_tasks if task.status == 'completed'])
    in_progress_tasks = len([task for task in job_tasks if task.status == 'in_progress'])
    claimed_tasks = len([task for task in job_tasks if task.status == 'claimed'])
    
    progress_percent = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
    
    # Get available cleaners not already on the team - Fix: extract user_id properly
    current_team_user_ids = [member.user_id for member in team_members]
    available_cleaners = User.query.filter(
        User.role == 'cleaner',
        ~User.id.in_(current_team_user_ids),
        User.active == True
    ).all()
    
    # Get active timers for real-time tracking - Fix: add explicit join condition
    active_timers = db.session.query(Timer, JobTask).join(
        JobTask, Timer.job_task_id == JobTask.id
    ).filter(
        JobTask.job_id == job_id,
        Timer.stopped_at == None
    ).all()
    
    return render_template('job_management.html',
                         job=job,
                         job_tasks=job_tasks,
                         team_members=team_members,
                         recent_activities=recent_activities,
                         available_cleaners=available_cleaners,
                         active_timers=active_timers,
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         in_progress_tasks=in_progress_tasks,
                         claimed_tasks=claimed_tasks,
                         progress_percent=progress_percent)


@app.route('/job/<int:job_id>/add_team_member', methods=['POST'])
@role_required('coordinator') 
def add_team_member(job_id):
    """Add a cleaner to the job team"""
    from models import Job, JobTeamMember, User
    
    job = Job.query.get_or_404(job_id)
    
    if job.coordinator_id != current_user.id:
        flash('Access denied. You must be the job coordinator.', 'error')
        return redirect(url_for('dashboard'))
    
    cleaner_id = request.form.get('cleaner_id', type=int)
    if not cleaner_id:
        flash('Please select a cleaner to add.', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    cleaner = User.query.get_or_404(cleaner_id)
    if cleaner.role != 'cleaner':
        flash('Only cleaners can be added to teams.', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    # Check if already on team
    existing = JobTeamMember.query.filter_by(job_id=job_id, user_id=cleaner_id).first()
    if existing:
        flash(f'{cleaner.name} is already on the team.', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    try:
        # Add to team
        team_member = JobTeamMember(
            job_id=job_id,
            user_id=cleaner_id,
            role='cleaner'
        )
        db.session.add(team_member)
        
        # Log activity
        from models import ActivityLog
        activity = ActivityLog(
            job_id=job_id,
            user_id=current_user.id,
            event_type='team_member_added',
            payload={'added_user_id': cleaner_id, 'added_user_name': cleaner.name}
        )
        db.session.add(activity)
        
        db.session.commit()
        flash(f'{cleaner.name} has been added to the team!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding team member: {str(e)}")
        flash('Failed to add team member. Please try again.', 'error')
    
    return redirect(url_for('job_management', job_id=job_id))


@app.route('/job/<int:job_id>/remove_team_member/<int:member_id>', methods=['POST'])
@role_required('coordinator')
def remove_team_member(job_id, member_id):
    """Remove a cleaner from the job team"""
    from models import Job, JobTeamMember, User, JobTask
    
    job = Job.query.get_or_404(job_id)
    
    if job.coordinator_id != current_user.id:
        flash('Access denied. You must be the job coordinator.', 'error')
        return redirect(url_for('dashboard'))
    
    # Find the team member
    team_member = JobTeamMember.query.filter_by(
        job_id=job_id, 
        user_id=member_id
    ).first_or_404()
    
    # Don't allow removing the coordinator
    if team_member.role == 'coordinator':
        flash('Cannot remove the job coordinator from the team.', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    # Check if user has active tasks
    active_tasks = JobTask.query.filter_by(
        job_id=job_id,
        assigned_to_id=member_id
    ).filter(JobTask.status.in_(['claimed', 'in_progress'])).all()
    
    if active_tasks:
        task_names = [f"Task {task.task_order + 1}" for task in active_tasks]
        flash(f'Cannot remove {team_member.user.name} - they have active tasks: {", ".join(task_names)}', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    try:
        user_name = team_member.user.name
        
        # Release any assigned tasks back to pending
        assigned_tasks = JobTask.query.filter_by(
            job_id=job_id,
            assigned_to_id=member_id
        ).all()
        
        for task in assigned_tasks:
            task.assigned_to_id = None
            task.status = 'pending'
            task.claimed_at = None
        
        # Remove from team
        db.session.delete(team_member)
        
        # Log activity
        from models import ActivityLog
        activity = ActivityLog(
            job_id=job_id,
            user_id=current_user.id,
            event_type='team_member_removed',
            payload={'removed_user_id': member_id, 'removed_user_name': user_name}
        )
        db.session.add(activity)
        
        db.session.commit()
        flash(f'{user_name} has been removed from the team.', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing team member: {str(e)}")
        flash('Failed to remove team member. Please try again.', 'error')
    
    return redirect(url_for('job_management', job_id=job_id))


@app.route('/job/<int:job_id>/assign_task/<int:job_task_id>', methods=['POST'])
@role_required('coordinator')
def assign_task(job_id, job_task_id):
    """Assign a specific task to a team member"""
    from models import Job, JobTask, JobTeamMember, User
    
    job = Job.query.get_or_404(job_id)
    
    if job.coordinator_id != current_user.id:
        flash('Access denied. You must be the job coordinator.', 'error')
        return redirect(url_for('dashboard'))
    
    job_task = JobTask.query.get_or_404(job_task_id)
    if job_task.job_id != job_id:
        flash('Task does not belong to this job.', 'error')
        return redirect(url_for('job_management', job_id=job_id))
    
    assigned_user_id = request.form.get('assigned_user_id', type=int)
    
    if not assigned_user_id:
        # Unassign task
        job_task.assigned_to_id = None
        if job_task.status == 'claimed':
            job_task.status = 'pending'
            job_task.claimed_at = None
        flash_message = f'Task {job_task.task_order + 1} has been unassigned.'
        activity_payload = {'task_order': job_task.task_order, 'action': 'unassigned'}
    else:
        # Assign task to user
        user = User.query.get_or_404(assigned_user_id)
        
        # Verify user is on the team
        team_member = JobTeamMember.query.filter_by(
            job_id=job_id, 
            user_id=assigned_user_id
        ).first()
        
        if not team_member:
            flash(f'{user.name} is not on the job team.', 'error')
            return redirect(url_for('job_management', job_id=job_id))
        
        # Check if task is available for assignment
        if job_task.status not in ['pending', 'claimed']:
            flash('Task cannot be reassigned while in progress.', 'error')
            return redirect(url_for('job_management', job_id=job_id))
        
        job_task.assigned_to_id = assigned_user_id
        job_task.status = 'claimed'
        job_task.claimed_at = datetime.now(timezone.utc)
        flash_message = f'Task {job_task.task_order + 1} assigned to {user.name}.'
        activity_payload = {
            'task_order': job_task.task_order,
            'assigned_user_id': assigned_user_id,
            'assigned_user_name': user.name,
            'action': 'assigned'
        }
    
    try:
        # Log activity
        from models import ActivityLog
        activity = ActivityLog(
            job_id=job_id,
            user_id=current_user.id,
            event_type='task_assigned',
            payload=activity_payload
        )
        db.session.add(activity)
        
        db.session.commit()
        flash(flash_message, 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error assigning task: {str(e)}")
        flash('Failed to assign task. Please try again.', 'error')
    
    return redirect(url_for('job_management', job_id=job_id))


@app.route('/claim_task/<int:job_task_id>', methods=['POST'])
@login_required
def claim_task(job_task_id):
    """Allow cleaners to claim available tasks"""
    if current_user.role != 'cleaner':
        flash('Only cleaners can claim tasks.', 'error')
        return redirect(url_for('dashboard'))
    
    from models import JobTask, JobTeamMember
    
    # Find the task
    job_task = JobTask.query.get_or_404(job_task_id)
    
    # Check if user is on the job team
    team_member = JobTeamMember.query.filter_by(
        job_id=job_task.job_id, 
        user_id=current_user.id
    ).first()
    
    if not team_member:
        flash('You must be assigned to the job team to claim tasks.', 'error')
        return redirect(url_for('dashboard'))
    
    # Attempt to claim the task
    success, message = job_task.claim_by_user(current_user.id)
    
    if success:
        flash(f'Task claimed successfully! {message}', 'success')
    else:
        flash(f'Failed to claim task: {message}', 'error')
    
    return redirect(url_for('job_tasks', job_id=job_task.job_id))


@app.route('/release_task/<int:job_task_id>', methods=['POST'])
@login_required
def release_task(job_task_id):
    """Allow users to release their claimed tasks"""
    from models import JobTask
    
    job_task = JobTask.query.get_or_404(job_task_id)
    
    # Only allow releasing your own tasks
    if job_task.assigned_to_id != current_user.id:
        flash('You can only release tasks assigned to you.', 'error')
        return redirect(url_for('dashboard'))
    
    # Attempt to release the task
    success, message = job_task.release_by_user(current_user.id)
    
    if success:
        flash(f'Task released successfully! {message}', 'success')
    else:
        flash(f'Failed to release task: {message}', 'error')
    
    return redirect(url_for('job_tasks', job_id=job_task.job_id))


@app.route('/job/<int:job_id>/tasks')
@login_required
def job_tasks(job_id):
    """Display all tasks for a job with claiming interface"""
    from models import Job, JobTask, JobTeamMember, User
    
    job = Job.query.get_or_404(job_id)
    
    # Check if user is coordinator or team member
    is_coordinator = (current_user.role == 'coordinator' and job.coordinator_id == current_user.id)
    is_team_member = JobTeamMember.query.filter_by(
        job_id=job_id, 
        user_id=current_user.id
    ).first() is not None
    
    if not (is_coordinator or is_team_member):
        flash('Access denied. You must be assigned to this job.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all job tasks with their details
    job_tasks = JobTask.query.filter_by(job_id=job_id).order_by(JobTask.task_order).all()
    
    # Get team members for coordinator view
    team_members = []
    if is_coordinator:
        team_members = JobTeamMember.query.filter_by(job_id=job_id).join(User).all()
    
    return render_template('job_tasks.html', 
                         job=job, 
                         job_tasks=job_tasks,
                         team_members=team_members,
                         is_coordinator=is_coordinator,
                         is_team_member=is_team_member)


@app.route('/populate_tasks')
def populate_tasks():
    """Populate the database with tasks from the task library - development helper"""
    from models import Task
    
    try:
        # Clear existing tasks
        Task.query.delete()
        
        # Populate tasks from task_library
        for cleaning_type, tasks in task_library.items():
            for task_data in tasks:
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
        
        db.session.commit()
        task_count = Task.query.count()
        flash(f'Successfully populated {task_count} tasks in database!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Task population error: {str(e)}")
        flash('Failed to populate tasks.', 'error')
    
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('index'))

@app.route('/submitted')
def submitted():
    """Results page - redirect to home if accessed directly"""
    return redirect(url_for('index'))

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    flash('File is too large. Maximum file size is 16MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    app.logger.error(f"Server error: {str(e)}")
    flash('An internal server error occurred. Please try again.', 'error')
    return render_template('index.html'), 500
