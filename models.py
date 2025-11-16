# models.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# --- Association Table for Wishlist ---
# Links Users and Products (Many-to-Many).
# Must be defined before the models that use it.
wishlist_table = db.Table('wishlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

# --- Main User Model ---
# This single class represents all users: Admins, Farmers, and regular Users.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='user')
    status = db.Column(db.String(20), nullable=False, default='approved')
    upi_id = db.Column(db.String(100), nullable=True)
    
    # Profile fields (for users and farmers)
    phone = db.Column(db.String(20), nullable=True)
    address_line1 = db.Column(db.String(200), nullable=True)
    address_line2 = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    place = db.Column(db.String(100), nullable=True)
    pincode = db.Column(db.String(20), nullable=True)
    state = db.Column(db.String(100), nullable=True)

    # Farmer-specific verification fields
    govt_id_path = db.Column(db.String(200), nullable=True)
    agri_proof_path = db.Column(db.String(200), nullable=True)

    # Timestamp for "Member Since" feature
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    # --- Relationships ---
    
    # Messaging (One-to-Many, self-referential)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='author', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    
    # Wishlist (Many-to-Many)
    wishlist_items = db.relationship('Product', secondary=wishlist_table, lazy='dynamic')
    
    # Complaints (One-to-Many)
    complaints_made = db.relationship('Complaint', foreign_keys='Complaint.user_id', backref='complainant', lazy=True)
    complaints_received = db.relationship('Complaint', foreign_keys='Complaint.farmer_id', backref='reported_farmer', lazy=True)

    # Ratings (One-to-Many)
    ratings_given = db.relationship('Rating', foreign_keys='Rating.user_id', backref='rater', lazy=True)
    ratings_received = db.relationship('Rating', foreign_keys='Rating.farmer_id', backref='rated_farmer', lazy=True)

    # Orders (One-to-Many)
    orders = db.relationship('Order', backref='user', lazy=True)

    # --- Password Methods ---
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# In models.py
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_featured = db.Column(db.Boolean, default=False)
    
    # These are the new columns with their default values
    unit = db.Column(db.String(20), nullable=False, default='kg')
    sales_type = db.Column(db.String(20), nullable=False, default='retail')
    min_order_quantity = db.Column(db.Integer, nullable=False, default=1)
    
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # --- Relationships ---
    farmer = db.relationship('User', backref='products')
    order_items = db.relationship('OrderItem', backref='product')
class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_text = db.Column(db.Text, nullable=False)
    proof_path = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- Rating Model ---
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating_value = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- Order Model ---
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Pending')
    payment_method = db.Column(db.String(50), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    razorpay_order_id = db.Column(db.String(100), nullable=True, index=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    return_requested = db.Column(db.Boolean, default=False)
    return_reason = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")


# --- OrderItem Model ---
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

# --- Message Model ---
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))