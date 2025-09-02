import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import uuid

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

# Task library with cleaning tasks and time estimates
task_library = {
    "Final Clean": [
        {
            "task": "Polish mirrors, light fixtures, and shower glass",
            "time_per_100": 1.0,
            "instructions": "Use glass cleaner and microfiber cloth. Spray glass cleaner on mirrors and fixtures, wipe in circular motions to avoid streaks. Pay special attention to water spots and fingerprints."
        },
        {
            "task": "Deep clean sinks, vanities, and toilets",
            "time_per_100": 1.5,
            "instructions": "Apply bathroom cleaner inside and around bowl, under rim, and base. Scrub with toilet brush thoroughly. Clean vanity surfaces, faucets, and sink basin with appropriate cleaner."
        },
        {
            "task": "Vacuum and mop all floors",
            "time_per_100": 2.0,
            "instructions": "Vacuum all carpeted areas thoroughly, including corners and edges. Sweep hard floors first, then mop with appropriate floor cleaner. Pay attention to baseboards and corners."
        },
        {
            "task": "Dust all surfaces and baseboards",
            "time_per_100": 1.2,
            "instructions": "Use microfiber cloth to dust all horizontal surfaces including windowsills, light switches, door frames, and baseboards. Work from top to bottom to avoid re-dusting lower areas."
        },
        {
            "task": "Clean kitchen appliances and countertops",
            "time_per_100": 2.5,
            "instructions": "Wipe down all countertops with appropriate cleaner. Clean exterior of appliances including refrigerator, oven, microwave, and dishwasher. Clean sink and faucet thoroughly."
        },
        {
            "task": "Window cleaning (interior)",
            "time_per_100": 0.8,
            "instructions": "Clean interior windows with glass cleaner and squeegee or microfiber cloth. Remove any adhesive residue, paint spots, or construction debris from glass surfaces."
        },
        {
            "task": "Remove construction debris and dust",
            "time_per_100": 1.8,
            "instructions": "Remove all visible construction dust, debris, and materials. Wipe down all surfaces that may have accumulated dust during construction. Check corners and crevices."
        },
        {
            "task": "Final walkthrough and touch-ups",
            "time_per_100": 0.5,
            "instructions": "Conduct thorough walkthrough to identify any missed areas. Address any remaining cleaning needs and ensure all areas meet quality standards."
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
        # Formula: (square_footage / 100) * time_per_100
        estimated_minutes = (square_footage / 100) * task["time_per_100"]
        
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
        
        # Prepare data for results page
        job_data = {
            'client_name': client_name,
            'job_address': job_address,
            'cleaner_name': cleaner_name,
            'square_footage': square_footage,
            'cleaning_type': cleaning_type,
            'before_photo': before_photo_filename,
            'after_photo': after_photo_filename,
            'tasks': calculated_tasks,
            'total_estimated_minutes': round(total_estimated_minutes, 1),
            'total_estimated_hours': total_estimated_hours
        }
        
        return render_template('submitted.html', job_data=job_data)
        
    except Exception as e:
        app.logger.error(f"Error processing job submission: {str(e)}")
        flash('An error occurred while processing your submission. Please try again.', 'error')
        return redirect(url_for('index'))

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
