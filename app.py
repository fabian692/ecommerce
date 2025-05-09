from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shoes_store.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'customer'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

# Crear base de datos
with app.app_context():
    db.create_all()
    # Crear usuario admin por defecto si no existe
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

# Rutas
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        flash('Credenciales inválidas')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Usuario ya existe')
        else:
            user = User(
                username=username,
                password=generate_password_hash(password),
                role='customer'
            )
            db.session.add(user)
            db.session.commit()
            flash('Registro exitoso. Por favor, inicia sesión.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('index'))

# Rutas de administrador
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        product = Product(
            name=request.form['name'],
            price=float(request.form['price']),
            description=request.form['description'],
            stock=int(request.form['stock'])
        )
        db.session.add(product)
        db.session.commit()
        flash('Producto añadido exitosamente')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_product.html')

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.description = request.form['description']
        product.stock = int(request.form['stock'])
        db.session.commit()
        flash('Producto actualizado exitosamente')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_product.html', product=product)

@app.route('/admin/product/delete/<int:id>')
def delete_product(id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Producto eliminado exitosamente')
    return redirect(url_for('admin_dashboard'))

# Rutas de cliente
@app.route('/cart')
def cart():
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
    cart_items = Cart.query.filter_by(user_id=session['user_id']).all()
    total = 0
    for item in cart_items:
        product = Product.query.get(item.product_id)
        item.product = product
        total += product.price * item.quantity
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
    quantity = int(request.form['quantity'])
    product = Product.query.get_or_404(product_id)
    if product.stock < quantity:
        flash('No hay suficiente stock')
        return redirect(url_for('index'))
    
    cart_item = Cart.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=session['user_id'], product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    product.stock -= quantity
    db.session.commit()
    flash('Producto añadido al carrito')
    return redirect(url_for('index'))

@app.route('/cart/remove/<int:id>')
def remove_from_cart(id):
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
    cart_item = Cart.query.get_or_404(id)
    product = Product.query.get(cart_item.product_id)
    product.stock += cart_item.quantity
    db.session.delete(cart_item)
    db.session.commit()
    flash('Producto eliminado del carrito')
    return redirect(url_for('cart'))

if __name__ == '__main__':
    app.run(debug=True)