import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import uuid
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Task library with cleaning tasks and time estimates based on ResiBuilt specifications
task_library = {
    "Rough Clean": [
        {
            "task": "Clean all tubs and shower pans",
            "time_per_100": 1.2,
            "instructions": "Clean all tubs and shower pans thoroughly. Use appropriate cleaners that will not scratch, chip, or mar the surfaces. Remove all construction debris and residue."
        },
        {
            "task": "Clean window frames inside and outside",
            "time_per_100": 1.5,
            "instructions": "Clean all window frames both inside and outside, using care not to scratch frames. Use proper cleaning materials and techniques to avoid damage."
        },
        {
            "task": "Clean sliding glass door frames and panels",
            "time_per_100": 1.0,
            "instructions": "Clean sliding glass door frames and glass panels. Ensure all glass is left free of streaks and spots by using proper cleaning materials."
        },
        {
            "task": "Clean and vacuum window and door tracks",
            "time_per_100": 0.8,
            "instructions": "All window frames and sliding glass door tracks will be brushed clean and vacuumed. Remove all debris and construction materials from tracks."
        },
        {
            "task": "Clean cabinets and vanities inside and outside",
            "time_per_100": 2.0,
            "instructions": "All cabinets and vanities will be cleaned inside and outside. Interior should be vacuumed and washed or wiped clean. Use cleaner that will not scratch or mar doors, cabinets, or countertops. Clean tops of cabinets."
        },
        {
            "task": "Clean all drawers",
            "time_per_100": 0.6,
            "instructions": "All drawers will be vacuumed clean and wiped clean. Remove all construction debris and dust from drawer interiors."
        },
        {
            "task": "Clean closet shelves",
            "time_per_100": 0.4,
            "instructions": "All closet shelves to be wiped clean. Remove dust and construction debris from all shelf surfaces."
        },
        {
            "task": "Clean interior and exterior doors",
            "time_per_100": 1.0,
            "instructions": "All interior and exterior doors will be cleaned, including door knobs, lock sets and thresholds. Remove excess residue on hardware and thresholds (paint or joint compound) using appropriate cleaning agents."
        },
        {
            "task": "Clean electrical fixtures and appliances",
            "time_per_100": 1.2,
            "instructions": "All electrical fixtures, exposed light bulbs and appliances will be cleaned. Use appropriate cleaners and techniques to avoid damage to electrical components."
        },
        {
            "task": "Clean plumbing fixtures",
            "time_per_100": 1.5,
            "instructions": "All plumbing fixtures, including tubs, sinks and water closets, will be cleaned in a manner that will protect against scratching, chipping and marring. Use appropriate cleaners for each fixture type."
        }
    ],
    "Final Clean": [
        {
            "task": "Final polish of all surfaces",
            "time_per_100": 1.5,
            "instructions": "Perform final polishing of all cleaned surfaces. Ensure all areas meet quality standards and are ready for homeowner delivery."
        },
        {
            "task": "Final window and glass cleaning",
            "time_per_100": 1.0,
            "instructions": "Final cleaning of all windows and glass surfaces. Ensure streak-free finish and remove any remaining spots or residue."
        },
        {
            "task": "Final floor cleaning and inspection",
            "time_per_100": 2.0,
            "instructions": "Complete final cleaning of all floors. Vacuum carpets, mop hard surfaces, and inspect for any remaining debris or stains."
        }
    ],
    "QC Clean": [
        {
            "task": "Quality control inspection and touch-ups",
            "time_per_100": 1.0,
            "instructions": "Conduct thorough quality control inspection. Address any areas that do not meet standards and perform necessary touch-ups."
        },
        {
            "task": "Final quality verification",
            "time_per_100": 0.5,
            "instructions": "Final verification that all cleaning meets ResiBuilt quality standards before homeowner delivery."
        }
    ],
    "Spec Clean": [
        {
            "task": "Specification-based cleaning tasks",
            "time_per_100": 1.2,
            "instructions": "Complete any specific cleaning tasks as outlined in the project specifications. Address any special requirements or custom cleaning needs."
        },
        {
            "task": "Special attention areas",
            "time_per_100": 0.8,
            "instructions": "Focus on areas requiring special attention as specified in the project requirements. Ensure all specification requirements are met."
        }
    ]
}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    """Handle form submission and redirect to results"""
    try:
        # Get form data
        client_name = request.form.get('client_name', '').strip()
        job_address = request.form.get('job_address', '').strip()
        cleaner_name = request.form.get('cleaner_name', '').strip()
        square_footage = request.form.get('square_footage', type=int)
        cleaning_type = request.form.get('cleaning_type', '').strip()
        
        # Validate required fields
        if not all([client_name, job_address, cleaner_name, square_footage, cleaning_type]):
            flash('All fields are required.', 'error')
            return redirect(url_for('index'))
        
        if square_footage is None or square_footage <= 0:
            flash('Square footage must be greater than 0.', 'error')
            return redirect(url_for('index'))
        
        # Handle file uploads
        before_photo_filename = None
        after_photo_filename = None
        
        # Process before photo
        if 'before_photo' in request.files:
            before_file = request.files['before_photo']
            if before_file and before_file.filename and allowed_file(before_file.filename):
                # Generate unique filename
                file_extension = before_file.filename.rsplit('.', 1)[1].lower()
                before_photo_filename = f"before_{uuid.uuid4()}.{file_extension}"
                before_file.save(os.path.join(app.config['UPLOAD_FOLDER'], before_photo_filename))
        
        # Process after photo
        if 'after_photo' in request.files:
            after_file = request.files['after_photo']
            if after_file and after_file.filename and allowed_file(after_file.filename):
                # Generate unique filename
                file_extension = after_file.filename.rsplit('.', 1)[1].lower()
                after_photo_filename = f"after_{uuid.uuid4()}.{file_extension}"
                after_file.save(os.path.join(app.config['UPLOAD_FOLDER'], after_photo_filename))
        
        # Calculate task times
        calculated_tasks = calculate_task_times(cleaning_type, square_footage)
        total_estimated_minutes = sum(task['estimated_minutes'] for task in calculated_tasks)
        total_estimated_hours = round(total_estimated_minutes / 60, 2)
        
        # Store job data in session for individual task workflow
        session['job_data'] = {
            'client_name': client_name,
            'job_address': job_address,
            'cleaner_name': cleaner_name,
            'square_footage': square_footage,
            'cleaning_type': cleaning_type,
            'job_before_photo': before_photo_filename,
            'job_after_photo': after_photo_filename,
            'tasks': calculated_tasks,
            'total_estimated_minutes': round(total_estimated_minutes, 1),
            'total_estimated_hours': total_estimated_hours,
            'current_task_index': 0,
            'completed_tasks': [],
            'exceptions': []  # Store exceptions and issues
        }
        
        # Redirect to first task
        return redirect(url_for('task_page', task_index=0))
        
    except Exception as e:
        app.logger.error(f"Error processing job submission: {str(e)}")
        flash('An error occurred while processing your submission. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/task/<int:task_index>')
def task_page(task_index):
    """Individual task page with before/after photo uploads"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    job_data = session['job_data']
    tasks = job_data['tasks']
    
    if task_index >= len(tasks):
        # All tasks completed, show summary
        return redirect(url_for('job_complete'))
    
    current_task = tasks[task_index]
    progress = {
        'current': task_index + 1,
        'total': len(tasks),
        'percentage': round(((task_index) / len(tasks)) * 100)
    }
    
    return render_template('task.html', 
                         task=current_task, 
                         task_index=task_index,
                         job_data=job_data, 
                         progress=progress)

@app.route('/complete_task/<int:task_index>', methods=['POST'])
def complete_task(task_index):
    """Handle task completion with before/after photos"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    try:
        job_data = session['job_data']
        tasks = job_data['tasks']
        
        if task_index >= len(tasks):
            return redirect(url_for('job_complete'))
        
        current_task = tasks[task_index]
        
        # Handle before photo upload
        before_photo_filename = None
        if 'task_before_photo' in request.files:
            before_file = request.files['task_before_photo']
            if before_file and before_file.filename and allowed_file(before_file.filename):
                file_extension = before_file.filename.rsplit('.', 1)[1].lower()
                before_photo_filename = f"task_{task_index}_before_{uuid.uuid4()}.{file_extension}"
                before_file.save(os.path.join(app.config['UPLOAD_FOLDER'], before_photo_filename))
        
        # Handle after photo upload
        after_photo_filename = None
        if 'task_after_photo' in request.files:
            after_file = request.files['task_after_photo']
            if after_file and after_file.filename and allowed_file(after_file.filename):
                file_extension = after_file.filename.rsplit('.', 1)[1].lower()
                after_photo_filename = f"task_{task_index}_after_{uuid.uuid4()}.{file_extension}"
                after_file.save(os.path.join(app.config['UPLOAD_FOLDER'], after_photo_filename))
        
        # Store task completion data
        completed_task = {
            'task_index': task_index,
            'task_name': current_task['task'],
            'estimated_minutes': current_task['estimated_minutes'],
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

@app.route('/job_complete')
def job_complete():
    """Job completion summary page"""
    if 'job_data' not in session:
        flash('No active job found. Please start a new job.', 'error')
        return redirect(url_for('index'))
    
    job_data = session['job_data']
    return render_template('job_complete.html', job_data=job_data)

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
