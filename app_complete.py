import os 
import base64
import qrcode
import google.generativeai as genai
import json
import razorpay 
from flask import render_template
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
from flask_migrate import Migrate
from flask_migrate import upgrade as migrate_upgrade
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, flash, g
)
# In app_complete.py
from itsdangerous import URLSafeTimedSerializer # <-- ADD THIS IMPORT
# ... (all your other imports)
from werkzeug.utils import secure_filename
from models import db, User, Product, Complaint, Rating, Order, OrderItem, Message
from dotenv import load_dotenv
from flask import Response
from weasyprint import HTML
load_dotenv() 

# --- CONFIGURE THE API KEY ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create an instance of the Gemini Pro model
# FIXED: "models/gemini-2.5-pro" is not a valid model. 
# Use a valid model name like 'gemini-1.5-pro-latest' or 'gemini-pro'.
model = genai.GenerativeModel('gemini-1.5-pro-latest') 
# -----------------------------

# --- App Initialization & Configuration ---
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_strong_default_secret_key_123')

# FIXED: Use the 'default_db_path' variable you created.
default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agriconnect.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{default_db_path}')

# Setup the upload folder
upload_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = upload_folder_path
os.makedirs(upload_folder_path, exist_ok=True)
# FIXED: Removed duplicate os.makedirs() line

# --- Client Initializations ---
razorpay_client = razorpay.Client(
    auth=(os.getenv('RAZORPAY_KEY_ID'), os.getenv('RAZORPAY_KEY_SECRET'))
)
db.init_app(app)
migrate = Migrate(app, db) # Corrected: 'db' was missing

# --- Mail Configuration ---

def send_email(to, subject, template, **kwargs):
    """Send email using Gmail API on Render."""

    # 1. Load token.json from Render environment
    token_str = os.getenv("GMAIL_TOKEN_JSON")
    if not token_str:
        print("❌ ERROR: GMAIL_TOKEN_JSON not set in Render environment")
        return False
    
    try:
        # 2. Load credentials
        token = json.loads(token_str)
        creds = Credentials.from_authorized_user_info(
            token,
            ["https://www.googleapis.com/auth/gmail.send"]
        )

        # 3. Refresh token if expired
        if not creds.valid:
            if creds.refresh_token:
                creds.refresh(Request())
                # Optional: print("🔄 Token refreshed")
            else:
                print("❌ Gmail token expired & no refresh token available")
                return False

        # 4. Create Gmail API service
        service = build("gmail", "v1", credentials=creds)

        # 5. Render your HTML template
        html_body = render_template(template, **kwargs)

        # Create the MIME email
        message = EmailMessage()
        message["To"] = to
        message["From"] = os.getenv("MAIL_DEFAULT_SENDER")
        message["Subject"] = subject
        message.set_content("Your email client does not support HTML.")
        message.add_alternative(html_body, subtype="html")

        # Encode email
        raw_email = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {"raw": raw_email}

        # 6. Send email
        service.users().messages().send(
            userId="me",
            body=body
        ).execute()

        print(f"✅ Email sent successfully to {to}")
        return True

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

def allowed_file(filename):
    """Checks if the file's extension is allowed."""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.template_filter('format_currency')
def format_currency(value):
    """Custom template filter to format a number as currency."""
    if value is None:
        return "0.00"
    return f"{value:,.2f}"

# --- Public Routes ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Authentication ---

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    pwd = request.form.get('password')
    user = User.query.filter_by(email=email).first()

    if user and user.check_password(pwd):
        session['user_email'] = user.email
        session['role'] = user.role
        flash('Logged in successfully', 'success')

        # Redirect to the correct dashboard
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif user.role == 'user':
            return redirect(url_for('user_dashboard'))
        else:
            return redirect(url_for('index'))
    
    # --- THIS IS THE KEY CHANGE ---
    # If login fails, flash an error and redirect back to the homepage
    flash('Invalid email or password. Please try again.', 'danger')
    return redirect(url_for('index'))
    # If login fails, set an error message and show the login page again
    error = "Invalid email or password. Please try again."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

# In app_complete.py (after your /logout route)

def get_password_reset_serializer(salt='password-reset-salt'):
    """Returns a timed serializer for password reset tokens."""
    return URLSafeTimedSerializer(app.config['SECRET_KEY'], salt=salt)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Renders the 'forgot password' form and handles email submission."""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate a timed token (expires in 1 hour)
            s = get_password_reset_serializer()
            token = s.dumps(user.email, salt='password-reset-salt')
            
            # Create the reset link
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Send the email
            send_email(
                user.email, 
                "Password Reset Request for AgriConnect",
                'emails/reset_password_email.html',
                user=user, 
                reset_url=reset_url
            )

        # IMPORTANT: Show this message whether the user exists or not
        # This prevents attackers from guessing which emails are registered.
        flash("If an account with that email exists, a password reset link has been sent.", "info")
        return redirect(url_for('index'))

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Verifies the token and renders the 'reset password' form."""
    s = get_password_reset_serializer()
    
    try:
        # Check the token's validity (max_age=3600 seconds = 1 hour)
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        
        # Server-side password validation
        if not new_password or len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template('reset_password.html', token=token)

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            db.session.commit()
            flash("Your password has been updated successfully! You can now log in.", "success")
            return redirect(url_for('index'))
        else:
            flash("User not found.", "danger")
            return redirect(url_for('index'))

    # If GET request, just show the form
    return render_template('reset_password.html', token=token)  

# --- Registration ---
@app.route('/register_farmer', methods=['POST'])
def register_farmer():
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    city = request.form['city']
    place = request.form['place']
    password = request.form['password']

    if User.query.filter_by(email=email).first():
        flash("Email already registered", "danger")
        return redirect(url_for('index'))

    govt_id_file = request.files.get('govt_id')
    agri_proof_file = request.files.get('agri_proof')

    if not (govt_id_file and agri_proof_file and
            allowed_file(govt_id_file.filename) and allowed_file(agri_proof_file.filename)):
        flash("Both documents are required and must be valid file types (PNG, JPG, PDF).", "danger")
        return redirect(url_for('index'))

    filename1 = secure_filename(f"govt_id_{email}_{govt_id_file.filename}")
    govt_id_path = os.path.join(app.config['UPLOAD_FOLDER'], filename1)
    govt_id_file.save(govt_id_path)

    filename2 = secure_filename(f"agri_proof_{email}_{agri_proof_file.filename}")
    agri_proof_path = os.path.join(app.config['UPLOAD_FOLDER'], filename2)
    agri_proof_file.save(agri_proof_path)

    farmer = User(
        name=name,
        email=email,
        phone=phone,
        city=city,
        place=place,
        role="farmer",
        govt_id_path=govt_id_path,
        agri_proof_path=agri_proof_path,
        status="pending"
    )
    farmer.set_password(password)
    db.session.add(farmer)
    db.session.commit()
    flash("Farmer registration successful. Please wait for admin approval.", "success")
    return redirect(url_for('index'))

# In app_complete.py

@app.route('/register_user', methods=['POST'])
def register_user():
    """Registration for regular users/customers."""
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    
    # --- NEW: Get the added form fields ---
    phone = request.form.get('phone')
    city = request.form.get('city')
    place = request.form.get('place')
    # ------------------------------------

    if User.query.filter_by(email=email).first():
        flash("Email already registered", "danger")
        return redirect(url_for('index'))

    # --- NEW: Add fields to the User object ---
    user = User(
        name=name, 
        email=email, 
        role="user", 
        status="approved",
        phone=phone,
        city=city,
        place=place
    )
    # ----------------------------------------
    
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    flash("Registration successful! You can now log in.", "success")
    return redirect(url_for('index'))

# --- Complaints ---
@app.route('/report', methods=['GET', 'POST'])
def report_complaint():
    if 'user_email' not in session:
        flash("You must be logged in to file a complaint.", "warning")
        return redirect(url_for('index'))

    if request.method == 'POST':
        farmer_email = request.form.get('farmer_email')
        complaint_text = request.form.get('complaint_text')
        proof_file = request.files.get('proof_file')

        farmer = User.query.filter_by(email=farmer_email, role='farmer').first()
        if not farmer:
            flash(f"No farmer found with the email '{farmer_email}'.", "danger")
            return redirect(url_for('report_complaint'))

        complainant = User.query.filter_by(email=session['user_email']).first()

        if proof_file and allowed_file(proof_file.filename):
            filename = secure_filename(f"proof_{complainant.id}_{farmer.id}_{proof_file.filename}")
            proof_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            proof_file.save(proof_path)

            new_complaint = Complaint(
                complaint_text=complaint_text,
                proof_path=proof_path,
                user_id=complainant.id,
                farmer_id=farmer.id
            )
            db.session.add(new_complaint)
            db.session.commit()

            flash("Your complaint has been submitted and is pending review by an admin.", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid or missing proof file. Please upload PNG, JPG, or PDF.", "danger")
            return redirect(url_for('report_complaint'))

    return render_template('report_complaint.html')

# --- Ratings ---
@app.route('/rate-farmer')
def rate_farmer_page():
    if session.get('role') != 'user':
        flash("Only registered users can submit ratings.", "warning")
        return redirect(url_for('index'))
    farmers = User.query.filter_by(role='farmer', status='approved').all()
    return render_template('rate_farmer.html', farmers=farmers)

@app.route('/submit-rating', methods=['POST'])
def submit_rating():
    if session.get('role') != 'user':
        return redirect(url_for('index'))

    farmer_id = request.form.get('farmer_id')
    rating_value = request.form.get('rating_value')
    comment = request.form.get('comment')
    
    user = User.query.filter_by(email=session['user_email']).first()

    new_rating = Rating(
        farmer_id=farmer_id,
        user_id=user.id,
        rating_value=int(rating_value),
        comment=comment
    )
    db.session.add(new_rating)
    db.session.commit()

    flash("Thank you for your feedback!", "success")
    return redirect(url_for('index'))

# --- Admin Dashboard ---
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    farmers_pending = User.query.filter_by(role='farmer', status='pending').all()
    farmers_approved = User.query.filter_by(role='farmer', status='approved').all()
    farmers_rejected = User.query.filter_by(role='farmer', status='rejected').all()
    total_farmers = User.query.filter_by(role='farmer').count()

    complaints = Complaint.query.order_by(Complaint.timestamp.desc()).all()
    return_requests = Order.query.filter_by(return_requested=True, status="Return Requested").order_by(Order.order_date.desc()).all()
    
    return render_template(
        'admin_dashboard.html',
        farmer_count=total_farmers,
        approved_farmers=farmers_approved,
        pending_farmers=farmers_pending,
        rejected_farmers=farmers_rejected,
        complaints=complaints
    )

@app.route('/admin/delete_farmer/<email>', methods=['POST'])
def delete_farmer(email):
    if session.get('role') != 'admin':
        flash("You don't have permission to do that.", "danger")
        return redirect(url_for('index'))

    farmer_to_delete = User.query.filter_by(email=email, role='farmer').first()

    if farmer_to_delete:
        db.session.delete(farmer_to_delete)
        db.session.commit()
        flash(f"Farmer '{farmer_to_delete.name}' has been deleted.", "success")
    else:
        flash("Farmer not found.", "warning")

    return redirect(url_for('admin_dashboard'))

# In app_complete.py

@app.route('/approve/<email>')
def approve_farmer(email):
    # Security check to ensure only an admin is accessing this
    if session.get('role') != 'admin':
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('index'))

    # Find the specific user who is a farmer by their email
    farmer = User.query.filter_by(email=email, role='farmer').first()

    if farmer:
        # Update the farmer's status
        farmer.status = 'approved'
        db.session.commit()
        
        # Give feedback to the admin on the dashboard
        flash(f"Farmer '{farmer.name}' has been approved.", "success")
        
        # Send the approval email to the farmer
        send_email(farmer.email, "Your Application has been Approved!", 'emails/farmer_verified.html', farmer=farmer)
    else:
        flash("Farmer not found.", "danger")
        
    return redirect(url_for('admin_dashboard'))


@app.route('/reject/<email>')
def reject_farmer(email):
    # Security check to ensure only an admin is accessing this
    if session.get('role') != 'admin':
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('index'))

    # Find the specific user who is a farmer by their email
    farmer = User.query.filter_by(email=email, role='farmer').first()

    if farmer:
        # Update the farmer's status
        farmer.status = 'rejected'
        db.session.commit()

        # Give feedback to the admin on the dashboard
        flash(f"Farmer '{farmer.name}' has been rejected.", "warning")
        
        # Send the rejection email to the farmer
        send_email(farmer.email, "Update on Your Application", 'emails/farmer_verified.html', farmer=farmer)
    else:
        flash("Farmer not found.", "danger")
        
    return redirect(url_for('admin_dashboard'))

# --- Farmer Dashboard ---
# In app_complete.py

@app.route('/farmer-dashboard')
def farmer_dashboard():
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer to view this page.', 'danger')
        return redirect(url_for('index'))

    farmer = User.query.filter_by(email=session['user_email']).first()
    if not farmer:
        flash("Farmer profile not found.", "danger")
        return redirect(url_for('logout'))

    # Fetch farmer's products
    farmer_products = Product.query.filter_by(farmer_id=farmer.id).all()
    total_products = len(farmer_products)
    
    # Fetch all order items linked to this farmer's products
    farmer_order_items = db.session.query(OrderItem).join(Product).filter(Product.farmer_id == farmer.id).all()
    
    # Calculate total sales value
    total_sales_value = sum(item.price * item.quantity for item in farmer_order_items)
    
    # Calculate average rating
    ratings = Rating.query.filter_by(farmer_id=farmer.id).all()
    avg_rating = sum(r.rating_value for r in ratings) / len(ratings) if ratings else 0

    return render_template(
        'farmer_dashboard.html', 
        farmer=farmer,
        farmer_products=farmer_products,
        total_products=total_products,
        total_sales_value=total_sales_value,
        avg_rating=avg_rating,
        orders=farmer_order_items,
        # --- ADD THESE LINES BACK ---
        farmer_city=farmer.city, 
        farmer_state=farmer.state 
        # ---------------------------
    )
@app.route('/farmer-dashboard/add-product', methods=['GET', 'POST'])
def add_product_page():
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer to add products.', 'danger')
        return redirect(url_for('index'))
    
    # Fetch and validate the farmer at the beginning
    farmer = User.query.filter_by(email=session['user_email']).first()
    if not farmer:
        flash("Your session is invalid, please log in again.", "warning")
        return redirect(url_for('logout'))
    
    if request.method == 'POST':
        # Get all data from the form
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        category = request.form.get('category')
        image_file = request.files.get('image')
        
        # --- NEW FIELDS ---
        unit = request.form.get('unit')
        sales_type = request.form.get('sales_type')
        min_order_quantity = request.form.get('min_order_quantity')
        # ------------------

        # --- UPDATED VALIDATION ---
        if not all([name, description, price, quantity, category, image_file, unit, sales_type, min_order_quantity]):
            flash("All fields are required, including unit, sales type, and minimum order.", "danger")
            return redirect(url_for('add_product_page'))
        # --------------------------
        
        if not allowed_file(image_file.filename):
            flash("Invalid image file type. Please use PNG, JPG, or JPEG.", "danger")
            return redirect(url_for('add_product_page'))

        # Save the image file
        filename = secure_filename(f"product_{farmer.id}_{image_file.filename}")
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)

        # --- UPDATED PRODUCT CREATION ---
        new_product = Product(
            name=name,
            description=description,
            price=float(price),
            quantity=int(quantity),
            category=category,
            image_path=image_path,
            farmer_id=farmer.id,
            unit=unit,  # Added
            sales_type=sales_type,  # Added
            min_order_quantity=int(min_order_quantity)  # Added
        )
        # --------------------------------
        
        db.session.add(new_product)
        db.session.commit()

        flash("Product added successfully!", "success")
        return redirect(url_for('farmer_dashboard'))

    # This is for the GET request
    return render_template('add_product.html')
@app.route('/farmer-dashboard/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    # Security check: Ensure user is a logged-in farmer
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer.', 'danger')
        return redirect(url_for('index'))
    
    # Fetch the product from the database, or show a 404 error if not found
    product = Product.query.get_or_404(product_id)
    farmer = User.query.filter_by(email=session['user_email']).first()

    # Security check: Ensure the product belongs to the logged-in farmer
    if product.farmer_id != farmer.id:
        flash("You don't have permission to edit this product.", "danger")
        return redirect(url_for('farmer_dashboard'))

    # Handle the form submission
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.category = request.form.get('category')
        product.price = float(request.form.get('price'))
        product.quantity = int(request.form.get('quantity'))
        
        # Optional: Handle image update
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            # You could add logic here to delete the old image if you want
            filename = secure_filename(f"product_{farmer.id}_{image_file.filename}")
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            product.image_path = image_path

        db.session.commit()
        flash("Product updated successfully!", "success")
        return redirect(url_for('farmer_dashboard'))

    # If GET request, show the form pre-filled with product data
    return render_template('edit_product.html', product=product)
@app.route('/farmer-dashboard/delete-product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    # Security check: Ensure user is a logged-in farmer
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer.', 'danger')
        return redirect(url_for('index'))

    # Fetch the product from the database
    product = Product.query.get_or_404(product_id)
    farmer = User.query.filter_by(email=session['user_email']).first()

    # Security check: Ensure the product belongs to the logged-in farmer
    if product.farmer_id != farmer.id:
        flash("You don't have permission to delete this product.", "danger")
        return redirect(url_for('farmer_dashboard'))
    
    # Optional but recommended: Delete the product's image file from the server
    try:
        if product.image_path and os.path.exists(product.image_path):
            os.remove(product.image_path)
    except Exception as e:
        print(f"Error deleting file {product.image_path}: {e}")

    # Delete the product from the database
    db.session.delete(product)
    db.session.commit()
    
    flash(f"Product '{product.name}' has been deleted.", "success")
    return redirect(url_for('farmer_dashboard'))
    
    # In app_complete.py, add this with your other farmer routes

@app.route('/farmer-dashboard/edit-profile', methods=['GET', 'POST'])
def edit_farmer_profile():
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer to edit your profile.', 'danger')
        return redirect(url_for('index'))
    
    # Get the farmer from the database
    farmer = User.query.filter_by(email=session['user_email']).first()
    if not farmer:
        return redirect(url_for('logout'))

    # Handle the form submission when the farmer saves changes
    if request.method == 'POST':
        farmer.name = request.form.get('name')
        farmer.phone = request.form.get('phone')
        farmer.city = request.form.get('city')
        farmer.place = request.form.get('place')
        farmer.upi_id = request.form.get('upi_id')
        db.session.commit()
        flash("Your profile has been updated successfully!", "success")
        return redirect(url_for('farmer_dashboard'))

    # If it's a GET request, just show the form with the farmer's current data
    return render_template('edit_farmer_profile.html', farmer=farmer)
# --- Serve Uploaded Files ---
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
# --- NEW: Shopping Cart Routes ---
@app.route('/cart')
def view_cart():
    if 'cart' not in session or not session['cart']:
        return render_template('cart.html', cart_items=[], total_price=0)

    cart_items = []
    total_price = 0
    for product_id, quantity in session['cart'].items():
        product = Product.query.get(product_id)
        if product:
            item_total = product.price * quantity
            cart_items.append({'product': product, 'quantity': quantity, 'total': item_total})
            total_price += item_total
            
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_email' not in session or 'cart' not in session or not session['cart']:
        flash("Your cart is empty or you are not logged in.", "warning")
        return redirect(url_for('product_marketplace'))
    
    user = User.query.filter_by(email=session['user_email']).first()
    cart_items = session['cart']
    
    # --- Get all form data (address, payment, etc.) ---
    payment_method = request.form.get('payment_method')
    address_line1 = request.form.get('address_line1')
    address_line2 = request.form.get('address_line2')
    city = request.form.get('city')
    state = request.form.get('state')
    pincode = request.form.get('pincode')
    phone = request.form.get('phone')
    shipping_address = f"{address_line1}\n{address_line2 or ''}\n{city}, {state} - {pincode}\nPhone: {phone}"

    # --- Check for UPI availability (as before) ---
    first_product_id = next(iter(cart_items))
    first_product = Product.query.get(first_product_id)
    if not first_product:
        flash("An item in your cart is no longer available.", "danger")
        return redirect(url_for('view_cart'))
    farmer_to_pay = User.query.get(first_product.farmer_id)
    
    if payment_method == 'UPI' and not farmer_to_pay.upi_id:
        flash(f"Sorry, farmer {farmer_to_pay.name} has not set up UPI payments. Please choose COD.", "danger")
        return redirect(url_for('view_cart'))

    # --- Check stock and calculate total (as before) ---
    total_amount = 0
    for product_id, quantity in cart_items.items():
        product = Product.query.get(product_id)
        if product.quantity < quantity:
            flash(f"Not enough stock for {product.name}. Only {product.quantity} left.", "danger")
            return redirect(url_for('view_cart'))
        total_amount += product.price * quantity

    # --- Create the Order in our database (as 'Pending') ---
    new_order = Order(
        user_id=user.id, 
        total_amount=total_amount,
        payment_method=payment_method,
        shipping_address=shipping_address,
        status="Pending" # Set initial status to Pending
    )
    db.session.add(new_order)
    db.session.flush()

    for product_id, quantity in cart_items.items():
        product = Product.query.get(product_id)
        order_item = OrderItem(
            order_id=new_order.id, product_id=product.id,
            quantity=quantity, price=product.price
        )
        product.quantity -= quantity # Hold the stock
        db.session.add(order_item)
    
    # Save the user's address for next time
    user.address_line1 = address_line1
    user.address_line2 = address_line2
    user.city = city
    user.state = state
    user.pincode = pincode
    user.phone = phone
    
    db.session.commit()
    session.pop('cart', None) # Clear the cart

    # --- NEW: Payment Gateway Logic ---
    
    # If COD, the order is complete
    if new_order.payment_method == 'COD':
        new_order.status = 'Processing' # Update status from Pending
        db.session.commit()
        # Send emails
        send_email(user.email, f"Your Order #{new_order.id} is Confirmed!", 'emails/order_confirmation_user.html', user=user, order=new_order)
        send_email(farmer_to_pay.email, f"You Have a New Order! #{new_order.id}", 'emails/new_order_farmer.html', farmer=farmer_to_pay, order=new_order)
        flash("Your order has been placed successfully!", "success")
        return redirect(url_for('user_dashboard'))

    # If UPI/Online, create a Razorpay order
    if new_order.payment_method == 'UPI':
        try:
            razorpay_order = razorpay_client.order.create({
                "amount": int(total_amount * 100),  # Amount in paisa
                "currency": "INR",
                "receipt": f"order_{new_order.id}",
                "notes": {
                    "order_id": new_order.id,
                    "user_id": user.id,
                    "email": user.email
                }
            })
            
            # Store Razorpay order ID for verification
            new_order.razorpay_order_id = razorpay_order['id']
            db.session.commit()

            # Render the payment processing page
            return render_template('process_payment.html',
                                   order=new_order,
                                   razorpay_order_id=razorpay_order['id'],
                                   razorpay_key=os.getenv('RAZORPAY_KEY_ID'),
                                   amount=int(total_amount * 100),
                                   user=user)
        
        except Exception as e:
            print(f"Error creating Razorpay order: {e}")
            flash("Error connecting to payment gateway. Please try again.", "danger")
            return redirect(url_for('view_cart'))
    
    return redirect(url_for('index')) # Fallback


# --- NEW: Route to handle payment verification ---
@app.route('/payment-verification', methods=['POST'])
def payment_verification():
    data = request.form
    try:
        # Verify the payment signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })

        # --- PAYMENT IS SUCCESSFUL ---
        razorpay_order_id = data['razorpay_order_id']
        order = Order.query.filter_by(razorpay_order_id=razorpay_order_id).first()
        
        if order:
            order.status = 'Processing' # Update status from Pending to Processing
            order.razorpay_payment_id = data['razorpay_payment_id']
            db.session.commit()

            # Send emails
            user = User.query.get(order.user_id)
            farmer = order.items[0].product.farmer
            send_email(user.email, f"Your Order #{order.id} is Confirmed!", 'emails/order_confirmation_user.html', user=user, order=order)
            send_email(farmer.email, f"You Have a New Order! #{order.id}", 'emails/new_order_farmer.html', farmer=farmer, order=order)

            flash("Payment successful! Your order is confirmed.", "success")
            return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        flash("Payment verification failed. Please contact support.", "danger")
        return redirect(url_for('view_cart'))

    flash("Invalid payment verification.", "danger")
    return redirect(url_for('view_cart'))
@app.route('/payment/<int:order_id>')
def payment_page(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Get the farmer's UPI ID (assuming single-farmer order)
    first_item = order.items[0]
    farmer = User.query.get(first_item.product.farmer_id)

    # Construct the UPI payment string
    upi_string = f"upi://pay?pa={farmer.upi_id}&pn={farmer.name.replace(' ', '%20')}&am={order.total_amount}&cu=INR&tn=Order{order.id}"
    
    # Generate QR Code
    qr_img = qrcode.make(upi_string)
    qr_filename = f"qr_order_{order.id}.png"
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
    qr_img.save(qr_path)
    
    return render_template('payment.html', order=order, farmer=farmer, qr_filename=qr_filename)
# In app_complete.py, add this new route

# In app_complete.py
# In app_complete.py, add this new route with your other routes

@app.route('/order/update-status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    # Security check: Ensure user is a logged-in farmer
    if session.get('role') != 'farmer':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))

    # Get the new status from the form
    new_status = request.form.get('status')
    order = Order.query.get_or_404(order_id)
    
    # Get the customer who placed the order
    user = User.query.get(order.user_id)
    if not user:
        flash("Could not find the customer for this order.", "danger")
        return redirect(url_for('farmer_dashboard'))

    # Security check: Ensure the order belongs to this farmer
    farmer = User.query.filter_by(email=session['user_email']).first()
    is_farmers_order = any(item.product.farmer_id == farmer.id for item in order.items)

    if order and new_status and is_farmers_order:
        # Update status and save
        order.status = new_status
        db.session.commit()
        
        # Send email notification to the customer
        send_email(
            user.email, 
            f"Your Order #{order.id} is now '{new_status}'", 
            'emails/order_status_update.html', 
            user=user, 
            order=order
        )
        
        flash(f"Order #{order.id} status updated to '{new_status}'.", "success")
    else:
        flash("Could not update order status.", "danger")

    return redirect(url_for('farmer_dashboard'))
# In app_complete.py

@app.route('/farmer-dashboard/ai-tools', methods=['GET', 'POST'])
def ai_tools():
    if session.get('role') != 'farmer':
        return redirect(url_for('index'))
    
    farmer = User.query.filter_by(email=session['user_email']).first()
    farmer_city = farmer.city
    farmer_state = farmer.state
    
    price_rec = None
    demand_forecast = None
    category = None # <-- NEW: Variable to hold the category
    
    if request.method == 'POST':
        city_from_form = request.form.get('farmer_city')
        state_from_form = request.form.get('farmer_state')
        
        if 'submit_price' in request.form:
            base_price = float(request.form.get('base_price', 0))
            category = request.form.get('category', 'General') # <-- NEW: Store the category
            price_rec = get_ai_price_recommendation(category, base_price, city_from_form, state_from_form)
            
        elif 'submit_forecast' in request.form:
            category = request.form.get('forecast_category', 'General')
            demand_forecast = get_ai_demand_forecast(category, city_from_form, state_from_form)
            
    return render_template('ai_tools.html', 
                           price_rec=price_rec, 
                           demand_forecast=demand_forecast,
                           farmer_city=farmer_city,
                           farmer_state=farmer_state,
                           category=category # <-- NEW: Pass category to template
                           )
# In app_complete.py

def get_ai_price_recommendation(category, base_price, city, state):
    """Calls the Gemini Pro API to generate a full product listing."""
    if not isinstance(base_price, (int, float)) or base_price <= 0:
        return {'error': 'Invalid base price.'}

    current_date = datetime.now().strftime("%B %d, %Y")
    location = f"{city}, {state}, India" if city and state else "India"
    
    prompt = f"""
    As an agricultural market expert in India on {current_date}, analyze the following:
    - Product Category: '{category}'
    - Farmer's Base Price: ₹{base_price}
    - Farmer's Location: {location}

    Your task is to generate a complete product listing. Return ONLY a JSON object with these exact keys:
    1. "product_name": A short, attractive product name (e.g., "Fresh Red Onions (Ballari)").
    2. "product_description": A brief, one-sentence description (e.g., "Locally sourced, perfect for cooking.").
    3. "live_market_price": The current average market price in the farmer's location (e.g., "₹2400 - ₹2650 per quintal").
    4. "recommended_price": A float for the suggested selling price.
    5. "reasoning": A brief explanation for your recommendation.
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned_text)
        return result
    except Exception as e:
        print(f"Error calling Gemini API for price: {e}")
        # Fallback with basic generated content
        return {
            'product_name': f"Fresh {category}",
            'product_description': f"High-quality {category} from a local farmer.",
            'live_market_price': "N/A",
            'recommended_price': round(base_price * 1.1, 2),
            'reasoning': "API error, using default calculation."
        }
    # In app_complete.py, add this new route

# In app_complete.py

@app.route('/ai-add-product', methods=['POST'])
def ai_add_product():
    """Handles the form submitted from the AI tools page."""
    if session.get('role') != 'farmer':
        flash('You must be logged in as a farmer to add products.', 'danger')
        return redirect(url_for('index'))
    
    farmer = User.query.filter_by(email=session['user_email']).first()
    if not farmer:
        flash("Your session is invalid, please log in again.", "warning")
        return redirect(url_for('logout'))
    
    # Get all the data from the form (hidden and visible fields)
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    category = request.form.get('category')
    image_file = request.files.get('image')
    
    # --- ADDED NEW FIELDS ---
    unit = request.form.get('unit')
    sales_type = request.form.get('sales_type')
    min_order_quantity = request.form.get('min_order_quantity')
    # ------------------------

    # --- UPDATED VALIDATION ---
    if not all([name, description, price, quantity, category, image_file, unit, sales_type, min_order_quantity]):
        flash("All fields, including unit, sales type, and minimum order, are required.", "danger")
        return redirect(url_for('ai_tools'))
    # --------------------------
    
    if not allowed_file(image_file.filename):
        flash("Invalid image file type. Please use PNG, JPG, or JPEG.", "danger")
        return redirect(url_for('ai_tools'))

    # Save the image file
    filename = secure_filename(f"product_{farmer.id}_{image_file.filename}")
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(image_path)

    # --- UPDATED PRODUCT CREATION ---
    new_product = Product(
        name=name,
        description=description,
        price=float(price),
        quantity=int(quantity),
        category=category,
        image_path=image_path,
        farmer_id=farmer.id,
        unit=unit,  # Added
        sales_type=sales_type,  # Added
        min_order_quantity=int(min_order_quantity)  # Added
    )
    # --------------------------------
    
    db.session.add(new_product)
    db.session.commit()

    flash(f"Success! '{name}' has been added to the marketplace.", "success")
    return redirect(url_for('farmer_dashboard'))
def get_ai_demand_forecast(category, city, state):
    """Calls the Gemini Pro API for a location-aware demand forecast."""
    current_date = datetime.now().strftime("%B %d, %Y")
    location = f"{city}, {state}, India" if city and state else "India"

    prompt = f"""
    As an agricultural supply chain analyst in India on {current_date}, provide a demand forecast for products in the category '{category}' specifically for the region of {location}.
    Your analysis must consider local factors in {location} such as upcoming regional festivals, weather patterns, and local market dynamics.
    Return your response ONLY as a JSON object with three keys:
    1. "trend": a string ("Increasing", "Stable", or "Decreasing").
    2. "next_month_estimate": a string showing the percentage change (e.g., "+15%").
    3. "reasoning": a brief, one-sentence explanation referencing the specific location or local factors.
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        # Add farmer's city back into the response for display
        result = json.loads(cleaned_text)
        result['location'] = city
        return result
    except Exception as e:
        print(f"Error calling Gemini API for forecast: {e}")
        return {
            'trend': 'Stable',
            'next_month_estimate': '+5%',
            'reasoning': "API error, using default forecast.",
            'location': city
        }
# --- Add these new routes to the "Farmer Routes" section ---

@app.route('/farmers')
def farmers_directory():
    """Shows a list of all other approved farmers."""
    if session.get('role') != 'farmer':
        flash("You must be a farmer to access this page.", "warning")
        return redirect(url_for('index'))
    
    current_farmer = User.query.filter_by(email=session['user_email']).first()
    # Find all approved farmers except the current one
    other_farmers = User.query.filter(User.role == 'farmer', User.status == 'approved', User.id != current_farmer.id).all()
    
    return render_template('farmers_directory.html', farmers=other_farmers)

@app.route('/inbox')
def inbox():
    """Shows a list of conversations for the current farmer."""
    if session.get('role') != 'farmer':
        return redirect(url_for('index'))
    
    current_farmer = User.query.filter_by(email=session['user_email']).first()
    
    # This is a more complex query to get conversation partners
    sent_to = db.session.query(Message.recipient_id).filter(Message.sender_id == current_farmer.id)
    received_from = db.session.query(Message.sender_id).filter(Message.recipient_id == current_farmer.id)
    partner_ids = {item[0] for item in sent_to.union(received_from).all()}
    
    conversations = []
    if partner_ids:
        partners = User.query.filter(User.id.in_(partner_ids)).all()
        for partner in partners:
            unread_count = Message.query.filter_by(sender_id=partner.id, recipient_id=current_farmer.id, is_read=False).count()
            conversations.append({'partner': partner, 'unread': unread_count})

    return render_template('inbox.html', conversations=conversations)


@app.route('/messages/<int:recipient_id>', methods=['GET', 'POST'])
def conversation(recipient_id):
    """Shows a conversation and handles sending new messages."""
    if session.get('role') != 'farmer':
        return redirect(url_for('index'))

    current_farmer = User.query.filter_by(email=session['user_email']).first()
    other_farmer = User.query.get_or_404(recipient_id)

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            msg = Message(sender_id=current_farmer.id, recipient_id=recipient_id, content=content)
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('conversation', recipient_id=recipient_id))

    # Mark messages as read
    Message.query.filter_by(sender_id=recipient_id, recipient_id=current_farmer.id).update({'is_read': True})
    db.session.commit()

    # Fetch the full conversation
    messages = Message.query.filter(
        ((Message.sender_id == current_farmer.id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_farmer.id))
    ).order_by(Message.timestamp.asc()).all()
    
    return render_template('conversation.html', messages=messages, current_farmer=current_farmer, other_farmer=other_farmer)

@app.route('/cart/add/<int:product_id>')
# In app_complete.py

@app.route('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    # --- NEW: Check if the product exists first ---
    product = Product.query.get(product_id)
    if not product:
        flash("Sorry, that product does not exist.", "danger")
        return redirect(url_for('product_marketplace'))
    # ---------------------------------------------

    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    product_id_str = str(product_id)
    
    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    session.modified = True
    
    # We already know the product exists, so this is now safe
    return redirect(url_for('product_marketplace', added=product.name))
@app.before_request
def load_logged_in_user():
    """Load the current user from the session into the 'g' object."""
    user_email = session.get('user_email')
    
    if user_email is None:
        g.user = None
    else:
        g.user = User.query.filter_by(email=user_email).first()
# In app_complete.py, add this to your "User Routes" section

@app.route('/user-dashboard/edit-profile', methods=['GET', 'POST'])
def edit_user_profile():
    if not g.user or g.user.role != 'user':
        flash('You must be logged in as a user to edit your profile.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Update the user's details
        g.user.name = request.form.get('name')
        g.user.phone = request.form.get('phone')
        g.user.address_line1 = request.form.get('address_line1')
        g.user.address_line2 = request.form.get('address_line2')
        g.user.city = request.form.get('city')
        g.user.state = request.form.get('state')
        g.user.pincode = request.form.get('pincode')

        db.session.commit()
        flash("Your profile has been updated successfully!", "success")
        return redirect(url_for('user_dashboard'))

    # If it's a GET request, show the form
    return render_template('edit_user_profile.html', user=g.user)
# In app_complete.py, add these to your "User Routes" section

@app.route('/wishlist/toggle/<int:product_id>')
def toggle_wishlist(product_id):
    if not g.user:
        flash("You must be logged in to manage your wishlist.", "warning")
        return redirect(url_for('login'))

    product = Product.query.get_or_404(product_id)
    
    # Check if the product is already in the user's wishlist
    if product in g.user.wishlist_items:
        g.user.wishlist_items.remove(product)
        flash(f"Removed '{product.name}' from your wishlist.", "info")
    else:
        g.user.wishlist_items.append(product)
        flash(f"Added '{product.name}' to your wishlist!", "success")
        
    db.session.commit()
    # Redirect back to the page the user was on
    return redirect(request.referrer or url_for('product_marketplace'))

@app.route('/wishlist')
def view_wishlist():
    if not g.user:
        flash("You must be logged in to view your wishlist.", "warning")
        return redirect(url_for('login'))
    
    # The relationship makes getting the items simple
    items = g.user.wishlist_items.all()
    
    # We also need the user's full wishlist IDs for the marketplace logic
    wishlist_product_ids = {product.id for product in items}
    
    return render_template('wishlist.html', 
                           wishlist_items=items,
                           wishlist_product_ids=wishlist_product_ids)

@app.route('/products')
def product_marketplace():
    # Get all filter and sort parameters from the URL
    search_query = request.args.get('search')
    category_filter = request.args.get('category')
    location_filter = request.args.get('location')
    sort_by = request.args.get('sort_by', 'freshness') # Default to 'freshness'
    sales_type_filter = request.args.get('sales_type')
    # Base query for all approved products
    query = Product.query.join(User, User.id == Product.farmer_id).filter(User.status == 'approved')

    # Apply all filters to the query
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))
    if category_filter:
        # Check that the filter is not an empty string
        query = query.filter(Product.category == category_filter)
    if location_filter:
        # Check that the filter is not an empty string
        query = query.filter(User.city == location_filter)
    if sales_type_filter:
        query = query.filter(Product.sales_type == sales_type_filter)
    # Apply sorting to the query
    if sort_by == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Product.price.desc())
    else: 
        query = query.order_by(Product.timestamp.desc()) # Sort by freshness
    
    # Exclude products of the currently logged-in farmer
    if g.user and g.user.role == 'farmer':
        query = query.filter(Product.farmer_id != g.user.id)
    
    wishlist_product_ids = set()
    if g.user:
        wishlist_product_ids = {product.id for product in g.user.wishlist_items}

    products = query.all()

    # --- NEW: Get unique locations and categories for the dropdowns ---
    
    # Query for distinct cities from farmers who are approved
    locations = db.session.query(User.city).filter(User.role == 'farmer', User.status == 'approved', User.city != None).distinct().all()
    # Query for distinct categories from all products
    categories = db.session.query(Product.category).filter(Product.category != None).distinct().all()

    # Convert the query results (which are tuples) into simple lists
    available_locations = [loc[0] for loc in locations]
    available_categories = [cat[0] for cat in categories]
    # -----------------------------------------------------------------
    
    return render_template('product_marketplace.html', 
                           products=products,
                           wishlist_product_ids=wishlist_product_ids,
                           
                           # Pass the lists to the template
                           available_locations=available_locations,
                           available_categories=available_categories,
                           
                           # Pass the currently selected filter values back
                           search_query=search_query,
                           category_filter=category_filter,
                           location_filter=location_filter,
                           sort_by=sort_by
                           ,sales_type_filter=sales_type_filter)
@app.route('/farmer-profile/<int:farmer_id>')
def view_farmer_profile(farmer_id):
    # Fetch the farmer, or show a 404 error if not found
    farmer = User.query.filter_by(id=farmer_id, role='farmer', status='approved').first_or_404()
    
    # Fetch their products
    products = Product.query.filter_by(farmer_id=farmer.id).all()
    
    # Fetch their ratings and calculate the average
    ratings = Rating.query.filter_by(farmer_id=farmer.id).all()
    avg_rating = 0
    if ratings:
        avg_rating = sum(r.rating_value for r in ratings) / len(ratings)

    return render_template('farmer_profile.html', 
                           farmer=farmer, 
                           products=products, 
                           ratings=ratings, 
                           avg_rating=avg_rating)
# In app_complete.py, add this new route

@app.route('/order/invoice/<int:order_id>')
def download_invoice(order_id):
    # Security checks: ensure user is logged in
    if 'user_email' not in session:
        flash("You must be logged in to view an invoice.", "danger")
        return redirect(url_for('login'))

    user = g.user # Get user from @app.before_request
    order = Order.query.get_or_404(order_id)

    # Security check: ensure the user owns this order (or is an admin)
    if order.user_id != user.id and user.role != 'admin':
        flash("You do not have permission to view this invoice.", "danger")
        return redirect(url_for('user_dashboard'))

    # Render the HTML template with the order data
    html_string = render_template('invoice.html', order=order)

    # Generate the PDF in memory
    pdf = HTML(string=html_string).write_pdf()

    # Create a Flask response to send the PDF as a download
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment;filename=invoice_{order.id}.pdf"
        }
    )
@app.route('/user-dashboard')
def user_dashboard():
    # Security check: Ensure user is logged in with the correct role
    if 'user_email' not in session or session.get('role') != 'user':
        flash('You must be logged in as a user to view this page.', 'danger')
        return redirect(url_for('index')) 

    user = User.query.filter_by(email=session['user_email']).first()

    if not user:
        flash("Your session is invalid. Please log in again.", "warning")
        return redirect(url_for('logout'))

    # Fetch all orders placed by this user
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.order_date.desc()).all()
    
    # --- NEW: Fetch all complaints made by this user ---
    complaints = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.timestamp.desc()).all()
    # ----------------------------------------------------

    return render_template(
        'user_dashboard.html', 
        user=user, 
        orders=orders,
        complaints=complaints  # Pass the complaints list to the template
    )
# In app_complete.py, add these new routes

# --- NEW: Route for the FAQ page ---
@app.route('/faq')
def faq_page():
    """Renders the static FAQ and Guidelines page."""
    return render_template('faq.html')

# --- NEW: Route for the Contact Support page ---
@app.route('/contact-support', methods=['GET', 'POST'])
def contact_support():
    if request.method == 'POST':
        user_name = "Guest"
        user_email = request.form.get('email')
        subject = request.form.get('subject')
        message_body = request.form.get('message')
        
        # If the user is logged in, use their real name
        if g.user:
            user_name = g.user.name
            user_email = g.user.email

        if not all([user_email, subject, message_body]):
            flash("All fields are required.", "danger")
            return redirect(url_for('contact_support'))

        # Prepare and send the email to the admin
        admin_email = os.getenv('ADMIN_EMAIL')
        email_subject = f"Support Ticket: {subject}"
        
        # Send email to admin
        send_email(
            admin_email, 
            email_subject, 
            'emails/contact_support_email.html', 
            user_name=user_name, 
            user_email=user_email, 
            message_body=message_body
        )
        
        flash("Your message has been sent. Our support team will get back to you shortly.", "success")
        return redirect(url_for('index'))

    return render_template('contact_support.html')

# --- NEW: Route for a user to request a return ---
@app.route('/request-return/<int:order_id>', methods=['GET', 'POST'])
def request_return(order_id):
    if not g.user:
        flash("You must be logged in to request a return.", "warning")
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)

    # Security check: Ensure the user owns this order
    if order.user_id != g.user.id:
        flash("You do not have permission to modify this order.", "danger")
        return redirect(url_for('user_dashboard'))


# --- NEW: Route for the tutorials page ---
@app.route('/how-it-works/user')
def how_it_works_user():
    """How It Works page for Users"""
    return render_template('tutorials_user.html')


@app.route('/how-it-works/farmer')
def how_it_works_farmer():
    """How It Works page for Farmers"""
    return render_template('tutorials_farmer.html')
with app.app_context():
    # Use db.create_all() to ensure all tables exist
    # This is simpler and more reliable for local development
    print("Ensuring database tables exist...")
    db.create_all()
    print("Database tables are ready.")

    # Get admin credentials from Environment Variables
    admin_email = os.getenv('ADMIN_EMAIL')
    admin_pass = os.getenv('ADMIN_PASS')

    if admin_email and admin_pass:
        # Check if the admin user already exists
        if not User.query.filter_by(email=os.getenv('ADMIN_EMAIL')).first():
            print(f"Admin user not found. Creating one with email: {os.getenv('ADMIN_EMAIL')}")
            admin = User(name='Admin', email=os.getenv('ADMIN_EMAIL'), role='admin', status='approved')
            admin.set_password(os.getenv('ADMIN_PASS'))
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created successfully.")
        else:
            print("ℹ️ Admin user already exists.")
    else:
        print("⚠️ WARNING: ADMIN_EMAIL or ADMIN_PASS not set. Admin user not created.")
# ====================================================================

# ... (This should be followed by your @app.route functions) ...
# ====================================================================


# ====================================================================
# THIS BLOCK IS ONLY FOR RUNNING THE APP LOCALLY
# ====================================================================
if __name__ == '__main__':
    # This just runs the development server on your local machine.
    # Gunicorn does not run this block.
    app.run(debug=True)
# ====================================================================