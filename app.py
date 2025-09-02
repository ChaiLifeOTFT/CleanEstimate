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
    """Handle form submission and redirect to results"""
    try:
        # Get form data
        client_name = request.form.get('client_name', '').strip()
        job_address = request.form.get('job_address', '').strip()
        lot_number = request.form.get('lot_number', '').strip()
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
            'lot_number': lot_number,
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
            'exceptions': [],  # Store exceptions and issues
            'task_timers': {}  # Store timer data for each task
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
    
    # Get timer data for this task if it exists
    timer_data = job_data.get('task_timers', {}).get(str(task_index), None)
    
    return render_template('task.html', 
                         task=current_task, 
                         task_index=task_index,
                         job_data=job_data, 
                         progress=progress,
                         timer_data=timer_data)

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

@app.route('/start_task/<int:task_index>', methods=['POST'])
def start_task(task_index):
    """Start timer for a specific task"""
    if 'job_data' not in session:
        return {'error': 'No active job found'}, 400
    
    try:
        from datetime import datetime
        job_data = session['job_data']
        
        # Initialize task_timers if not exists
        if 'task_timers' not in job_data:
            job_data['task_timers'] = {}
        
        # Start timer for this task
        job_data['task_timers'][str(task_index)] = {
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'time_extensions': [],
            'actual_minutes': 0
        }
        
        session['job_data'] = job_data
        return {'success': True, 'start_time': job_data['task_timers'][str(task_index)]['start_time']}, 200
    except Exception as e:
        app.logger.error(f"Error starting task timer: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/request_more_time/<int:task_index>', methods=['POST'])
def request_more_time(task_index):
    """Request more time for a task"""
    if 'job_data' not in session:
        return {'error': 'No active job found'}, 400
    
    try:
        from datetime import datetime
        job_data = session['job_data']
        reason = request.json.get('reason', 'Additional time needed')
        additional_minutes = request.json.get('additional_minutes', 5)
        
        if str(task_index) in job_data.get('task_timers', {}):
            extension = {
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'additional_minutes': additional_minutes
            }
            job_data['task_timers'][str(task_index)]['time_extensions'].append(extension)
            session['job_data'] = job_data
            return {'success': True, 'extension': extension}, 200
        else:
            return {'error': 'Task timer not started'}, 400
            
    except Exception as e:
        app.logger.error(f"Error requesting more time: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/stop_task/<int:task_index>', methods=['POST'])
def stop_task(task_index):
    """Stop timer for a specific task"""
    if 'job_data' not in session:
        return {'error': 'No active job found'}, 400
    
    try:
        from datetime import datetime
        job_data = session['job_data']
        
        if str(task_index) in job_data.get('task_timers', {}):
            timer_data = job_data['task_timers'][str(task_index)]
            if timer_data['status'] == 'running':
                # Calculate actual time taken
                start_time = datetime.fromisoformat(timer_data['start_time'])
                end_time = datetime.now()
                actual_minutes = (end_time - start_time).total_seconds() / 60
                
                timer_data['end_time'] = end_time.isoformat()
                timer_data['actual_minutes'] = round(actual_minutes, 1)
                timer_data['status'] = 'completed'
                
                session['job_data'] = job_data
                return {'success': True, 'actual_minutes': timer_data['actual_minutes']}, 200
        
        return {'error': 'Task timer not found'}, 400
            
    except Exception as e:
        app.logger.error(f"Error stopping task timer: {str(e)}")
        return {'error': str(e)}, 500

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
