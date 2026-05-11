from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime, timedelta
import hashlib
import random
import logging

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-it-12345'

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect('delivery_service.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart

def add_to_cart(product_id, product_name, price, quantity=1):
    cart = get_cart()
    prod_id = str(product_id)
    if prod_id in cart:
        cart[prod_id]['quantity'] += quantity
    else:
        cart[prod_id] = {'name': product_name, 'price': float(price), 'quantity': quantity}
    save_cart(cart)

def clear_cart():
    session['cart'] = {}

@app.route('/')
def index():
    conn = get_db()
    products = conn.execute("SELECT * FROM товары WHERE наличие > 0").fetchall()
    conn.close()
    cart = get_cart()
    cart_count = sum(item['quantity'] for item in cart.values())
    return render_template('index.html', products=products, cart_count=cart_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        surname = request.form['surname']
        phone = request.form['phone']
        email = request.form['email']
        address = request.form['address']
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO клиенты (имя, фамилия, телефон, email, адрес, бонусы, категория)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, surname, phone, email, address, 0, 'обычный'))
            client_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT INTO users (client_id, username, password, role)
                VALUES (?, ?, ?, ?)
            ''', (client_id, username, hash_password(password), 'client'))
            
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Пользователь с таким именем уже существует"
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute('''
            SELECT * FROM users WHERE username = ? AND password = ?
        ''', (username, hash_password(password))).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['client_id'] = user['client_id']
            if user['role'] == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('profile'))
        return "Неверное имя пользователя или пароль"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('login'))
    
    conn = get_db()
    client = conn.execute('SELECT * FROM клиенты WHERE id = ?', (session['client_id'],)).fetchone()
    conn.close()
    return render_template('profile.html', client=client)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart_route(product_id):
    conn = get_db()
    product = conn.execute('SELECT * FROM товары WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    if product:
        quantity = int(request.form.get('quantity', 1))
        add_to_cart(product_id, product['название'], product['цена'], quantity)
    return redirect(url_for('index'))

@app.route('/cart')
def view_cart():
    cart = get_cart()
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('cart.html', cart=cart, total=total)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = get_cart()
    if str(product_id) in cart:
        del cart[str(product_id)]
        save_cart(cart)
    return redirect(url_for('view_cart'))

@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    quantity = int(request.form.get('quantity', 0))
    cart = get_cart()
    if str(product_id) in cart:
        if quantity <= 0:
            del cart[str(product_id)]
        else:
            cart[str(product_id)]['quantity'] = quantity
        save_cart(cart)
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('login'))
    
    cart = get_cart()
    if not cart:
        return redirect(url_for('index'))
    
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    payment_method = request.form.get('payment_method', 'cash')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO заказы (клиент_id, статус, сумма, способ_оплаты, примечания)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['client_id'], 'pending', total, payment_method, 'Через сайт'))
    order_id = cursor.lastrowid
    
    for prod_id, item in cart.items():
        cursor.execute('''
            INSERT INTO состав_заказа (заказ_id, товар_id, количество, цена_в_момент_заказа)
            VALUES (?, ?, ?, ?)
        ''', (order_id, int(prod_id), item['quantity'], item['price']))
    
    conn.commit()
    conn.close()
    
    clear_cart()
    return redirect(url_for('my_orders'))

@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('login'))
    
    conn = get_db()
    orders = conn.execute('''
        SELECT з.*, к.имя as курьер_имя, к.фамилия as курьер_фамилия
        FROM заказы з
        LEFT JOIN курьеры к ON з.курьер_id = к.id
        WHERE з.клиент_id = ? 
        ORDER BY з.дата_заказа DESC
    ''', (session['client_id'],)).fetchall()
    conn.close()
    return render_template('orders.html', orders=orders)

@app.route('/track_order/<int:order_id>')
def track_order(order_id):
    """Отслеживание статуса заказа в реальном времени"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    order = conn.execute('''
        SELECT з.*, к.имя as курьер_имя, к.фамилия as курьер_фамилия, 
               к.транспорт, к.рейтинг, к.телефон as курьер_телефон
        FROM заказы з
        LEFT JOIN курьеры к ON з.курьер_id = к.id
        WHERE з.id = ?
    ''', (order_id,)).fetchone()
    conn.close()
    
    if not order or (session.get('role') != 'admin' and order['клиент_id'] != session.get('client_id')):
        return "Доступ запрещён", 403
    
    return render_template('track_order.html', order=order, session=session)

# НОВЫЙ МАРШРУТ: Поэтапное обновление статуса заказа (курьер не меняется)
@app.route('/update_order_status_step/<int:order_id>')
def update_order_status_step(order_id):
    """Обновляет статус заказа поэтапно: pending → in_progress → delivered
       Если курьера нет, назначает случайного при первом обновлении"""
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('login'))
    
    # Проверяем, что заказ принадлежит клиенту
    conn = get_db()
    order = conn.execute('SELECT * FROM заказы WHERE id = ?', (order_id,)).fetchone()
    
    if not order or order['клиент_id'] != session.get('client_id'):
        conn.close()
        return "Доступ запрещён", 403
    
    current_status = order['статус']
    courier_id = order['курьер_id']
    
    # Определяем следующий статус
    status_order = ['pending', 'in_progress', 'delivered']
    
    if current_status in status_order:
        current_index = status_order.index(current_status)
        if current_index < len(status_order) - 1:
            next_status = status_order[current_index + 1]
        else:
            # Уже delivered, ничего не меняем
            conn.close()
            return redirect(url_for('track_order', order_id=order_id))
    else:
        # Если статус cancelled или другой, начинаем с pending
        next_status = 'pending'
    
    # Если курьера нет и статус меняется на in_progress или delivered, назначаем случайного курьера
    if courier_id is None and next_status in ['in_progress', 'delivered']:
        # Получаем всех активных курьеров
        couriers = conn.execute("SELECT id FROM курьеры WHERE статус = 'active'").fetchall()
        if couriers:
            random_courier = random.choice(couriers)
            courier_id = random_courier['id']
    
    # Обновляем статус и дату доставки если нужно
    if next_status == 'delivered':
        delivery_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if courier_id:
            conn.execute('''
                UPDATE заказы 
                SET статус = ?, дата_доставки = ?, курьер_id = ?
                WHERE id = ?
            ''', (next_status, delivery_date, courier_id, order_id))
        else:
            conn.execute('''
                UPDATE заказы 
                SET статус = ?, дата_доставки = ?
                WHERE id = ?
            ''', (next_status, delivery_date, order_id))
    else:
        if courier_id:
            conn.execute('''
                UPDATE заказы 
                SET статус = ?, курьер_id = ?
                WHERE id = ?
            ''', (next_status, courier_id, order_id))
        else:
            conn.execute('''
                UPDATE заказы 
                SET статус = ?
                WHERE id = ?
            ''', (next_status, order_id))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('track_order', order_id=order_id))

# Старый маршрут для случайного обновления (оставляем на всякий случай)
@app.route('/random_update_order_client/<int:order_id>')
def random_update_order_client(order_id):
    """Обновляет заказ случайным курьером и случайным статусом (только для клиента)"""
    if 'user_id' not in session or session.get('role') != 'client':
        return redirect(url_for('login'))
    
    # Проверяем, что заказ принадлежит клиенту
    conn = get_db()
    order_check = conn.execute('SELECT клиент_id FROM заказы WHERE id = ?', (order_id,)).fetchone()
    
    if not order_check or order_check['клиент_id'] != session.get('client_id'):
        conn.close()
        return "Доступ запрещён", 403
    
    # Получаем всех активных курьеров
    couriers = conn.execute("SELECT id FROM курьеры WHERE статус = 'active'").fetchall()
    
    if not couriers:
        conn.close()
        return "Нет доступных курьеров", 400
    
    # Выбираем случайного курьера
    random_courier = random.choice(couriers)
    courier_id = random_courier['id']
    
    # Возможные статусы
    statuses = ['pending', 'in_progress', 'delivered', 'cancelled']
    random_status = random.choice(statuses)
    
    # Обновляем заказ
    if random_status == 'delivered':
        delivery_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            UPDATE заказы 
            SET курьер_id = ?, статус = ?, дата_доставки = ?
            WHERE id = ?
        ''', (courier_id, random_status, delivery_date, order_id))
    else:
        conn.execute('''
            UPDATE заказы 
            SET курьер_id = ?, статус = ?
            WHERE id = ?
        ''', (courier_id, random_status, order_id))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('track_order', order_id=order_id))

# ------------------ АДМИН ПАНЕЛЬ ------------------
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    total_orders = conn.execute("SELECT COUNT(*) as count FROM заказы").fetchone()['count']
    total_clients = conn.execute("SELECT COUNT(*) as count FROM клиенты").fetchone()['count']
    total_couriers = conn.execute("SELECT COUNT(*) as count FROM курьеры").fetchone()['count']
    total_revenue = conn.execute("SELECT SUM(сумма) as sum FROM заказы WHERE статус = 'delivered'").fetchone()['sum'] or 0
    
    orders = conn.execute('''
        SELECT з.*, к.имя as клиент_имя, к.фамилия as клиент_фамилия,
               кур.имя as курьер_имя, кур.фамилия as курьер_фамилия,
               кур.телефон as курьер_телефон
        FROM заказы з
        LEFT JOIN клиенты к ON з.клиент_id = к.id
        LEFT JOIN курьеры кур ON з.курьер_id = кур.id
        ORDER BY з.дата_заказа DESC
    ''').fetchall()
    
    clients = conn.execute("SELECT * FROM клиенты").fetchall()
    couriers = conn.execute("SELECT * FROM курьеры ORDER BY занятость ASC, рейтинг DESC").fetchall()
    products = conn.execute("SELECT * FROM товары").fetchall()
    
    conn.close()
    
    return render_template('admin.html', 
                         total_orders=total_orders,
                         total_clients=total_clients,
                         total_couriers=total_couriers,
                         total_revenue=total_revenue,
                         orders=orders,
                         clients=clients,
                         couriers=couriers,
                         products=products)

@app.route('/admin/update_order_status', methods=['POST'])
def update_order_status():
    """Обновление статуса и курьера заказа админом"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    order_id = request.form.get('order_id')
    status = request.form.get('status')
    courier_id = request.form.get('courier_id')
    
    if not order_id:
        return redirect(url_for('admin_panel'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Обновляем курьера, если он указан
    if courier_id and courier_id != '':
        cursor.execute('UPDATE заказы SET курьер_id = ? WHERE id = ?', (courier_id, order_id))
    elif courier_id == '':
        # Если выбрано "Без курьера", устанавливаем NULL
        cursor.execute('UPDATE заказы SET курьер_id = NULL WHERE id = ?', (order_id,))
    
    # Обновляем статус и дату доставки
    if status == 'delivered':
        delivery_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('UPDATE заказы SET статус = ?, дата_доставки = ? WHERE id = ?', 
                      (status, delivery_date, order_id))
    else:
        cursor.execute('UPDATE заказы SET статус = ? WHERE id = ?', (status, order_id))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    price = float(request.form.get('price'))
    weight = float(request.form.get('weight')) if request.form.get('weight') else None
    category = request.form.get('category')
    stock = int(request.form.get('stock', 0))
    
    conn = get_db()
    conn.execute('''
        INSERT INTO товары (название, описание, цена, вес, категория, наличие)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, description, price, weight, category, stock))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    price = float(request.form.get('price'))
    stock = int(request.form.get('stock', 0))
    
    conn = get_db()
    conn.execute('UPDATE товары SET название = ?, цена = ?, наличие = ? WHERE id = ?',
                 (name, price, stock, product_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_product/<int:product_id>')
def delete_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute('DELETE FROM товары WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_courier', methods=['POST'])
def add_courier():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    surname = request.form.get('surname')
    phone = request.form.get('phone')
    email = request.form.get('email')
    transport = request.form.get('transport')
    
    conn = get_db()
    conn.execute('''
        INSERT INTO курьеры (имя, фамилия, телефон, email, статус, транспорт)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, surname, phone, email, 'active', transport))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/update_courier/<int:courier_id>', methods=['POST'])
def update_courier(courier_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    status = request.form.get('status')
    занятость = int(request.form.get('занятость', 0))
    
    conn = get_db()
    conn.execute('UPDATE курьеры SET статус = ?, занятость = ? WHERE id = ?',
                 (status, занятость, courier_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_courier/<int:courier_id>')
def delete_courier(courier_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    # Сначала обновляем заказы, убираем ссылку на удаляемого курьера
    conn.execute('UPDATE заказы SET курьер_id = NULL WHERE курьер_id = ?', (courier_id,))
    # Затем удаляем курьера
    conn.execute('DELETE FROM курьеры WHERE id = ?', (courier_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Сервер доставки еды запускается...")
    print("📱 Откройте браузер и перейдите по адресу: http://localhost:5000")
    print("=" * 50)
    print("✨ НОВЫЙ ФУНКЦИОНАЛ:")
    print("✅ Кнопка 'Обновить статус' меняет статус ПОЭТАПНО: pending → in_progress → delivered")
    print("✅ Курьер НЕ МЕНЯЕТСЯ, если уже назначен")
    print("✅ Если курьера нет, он назначается случайно при первом обновлении до in_progress")
    print("=" * 50)
    print("👤 Тестовые пользователи: user1, user2, user3, user4, user5 (пароль: password123)")
    print("👑 Админ: login='admin', password='admin123'")
    print("=" * 50)
    app.run(debug=True, port=5000)