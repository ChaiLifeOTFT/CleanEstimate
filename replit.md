# Drake's Precision Cleaning App

## Overview

A Flask-based web application designed for Drake's Precision Cleaning business to estimate job completion times and manage cleaning tasks. The application provides a professional interface for creating detailed job estimates based on square footage, cleaning type, and specific task requirements. It features a task library with standardized cleaning procedures and time calculations, file upload capabilities for job documentation, and generates comprehensive job summaries with task breakdowns and instructions.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

**Web Framework**: Built using Flask, a lightweight Python web framework chosen for its simplicity and rapid development capabilities. The application follows a traditional server-side rendering pattern with Jinja2 templates.

**Frontend Architecture**: Uses Bootstrap 5 with a dark theme for responsive design and Font Awesome for consistent iconography. The interface is designed as a single-page application with form-based interactions, providing a clean and professional appearance suitable for business use.

**File Handling**: Implements secure file upload functionality with configurable restrictions on file types (images only: png, jpg, jpeg, gif, webp) and size limits (16MB maximum). Files are stored in a local `static/uploads` directory with secure filename handling to prevent security vulnerabilities.

**Data Management**: Uses in-memory data structures with a predefined task library containing cleaning tasks, time estimates per 100 square feet, and detailed instructions. Job data is processed and calculated dynamically without persistent storage, making each session stateless.

**Task Estimation System**: Implements a time calculation algorithm that scales cleaning tasks based on square footage. Each task in the library includes a `time_per_100` value that gets multiplied by the actual square footage ratio to provide accurate time estimates.

**Session Management**: Utilizes Flask's built-in session handling with flash messages for user feedback and error handling. The application includes proper error handling for file uploads and form validation.

## External Dependencies

**CDN Resources**: 
- Bootstrap 5 CSS framework via Replit's CDN for consistent styling
- Font Awesome 6.4.0 for iconography via CDNJS

**Python Libraries**:
- Flask for web framework functionality
- Werkzeug for secure filename handling and utilities
- UUID for unique identifier generation
- Standard library modules (os, logging) for system operations

**Environment Configuration**: Supports environment-based configuration for session secrets, with fallback to development defaults for local testing.

**File System**: Relies on local file system for upload storage, with automatic directory creation for the uploads folder.