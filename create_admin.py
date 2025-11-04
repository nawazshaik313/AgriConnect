# Save this file as create_admin.py
from app_complete import app, db
from models import User

print("--- Admin Creation Script Started ---")

# This is the crucial part: it creates the application context
with app.app_context():
    print("1. Application context entered.")
    
    # Create all database tables if they don't exist
    db.create_all()
    print("2. `db.create_all()` called. Tables ensured.")
    
    admin_email = 'admin@agriconnect.com' # Use a more official email
    
    # Check if the admin user already exists
    existing_admin = User.query.filter_by(email=admin_email).first()
    
    if not existing_admin:
        admin_email = 'admin@agriconnect.com'
        # If no admin exists, create one
        admin = User(name='Admin', email=admin_email, role='admin')
        admin.set_password('admin123') # Set a secure password
        
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created successfully!")
    else:
        print("ℹ️ Admin user already exists. No action taken.")

print("--- Script Finished ---")