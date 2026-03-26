# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Функция для подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('delivery_service.db')
    conn.row_factory = sqlite3.Row
    return conn

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# ==================== КУРЬЕРЫ ====================
@app.route('/couriers')
def couriers():
    conn = get_db_connection()
    couriers = conn.execute('SELECT * FROM курьеры ORDER BY id').fetchall()
    conn.close()
    return render_template('couriers.html', couriers=couriers)

@app.route('/add_courier', methods=['GET', 'POST'])
def add_courier():
    if request.method == 'POST':
        имя = request.form['имя']
        фамилия = request.form['фамилия']
        телефон = request.form['телефон']
        email = request.form.get('email', '')
        статус = request.form.get('статус', 'active')
        транспорт = request.form.get('транспорт', '')
        рейтинг = float(request.form.get('рейтинг', 5.0))
        занятость = int(request.form.get('занятость', 0))
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO курьеры (имя, фамилия, телефон, email, статус, транспорт, рейтинг, занятость)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (имя, фамилия, телефон, email, статус, транспорт, рейтинг, занятость))
        conn.commit()
        conn.close()
        flash('Курьер успешно добавлен!', 'success')
        return redirect(url_for('couriers'))
    
    return render_template('add_courier.html')

@app.route('/clients')
def clients():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM клиенты ORDER BY id').fetchall()
    conn.close()
    return render_template('clients.html', clients=clients)

@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        имя = request.form['имя']
        фамилия = request.form['фамилия']
        телефон = request.form['телефон']
        email = request.form.get('email', '')
        адрес = request.form.get('адрес', '')
        бонусы = int(request.form.get('бонусы', 0))
        категория = request.form.get('категория', 'обычный')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO клиенты (имя, фамилия, телефон, email, адрес, бонусы, категория)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (имя, фамилия, телефон, email, адрес, бонусы, категория))
        conn.commit()
        conn.close()
        flash('Клиент успешно добавлен!', 'success')
        return redirect(url_for('clients'))
    
    return render_template('add_client.html')

# ==================== ТОВАРЫ ====================
@app.route('/products')
def products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM товары ORDER BY id').fetchall()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        название = request.form['название']
        описание = request.form.get('описание', '')
        цена = float(request.form['цена'])
        вес = float(request.form.get('вес', 0.0)) if request.form.get('вес') else None
        категория = request.form.get('категория', '')
        наличие = int(request.form.get('наличие', 0))
        рейтинг = float(request.form.get('рейтинг', 0.0))
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO товары (название, описание, цена, вес, категория, наличие, рейтинг)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (название, описание, цена, вес, категория, наличие, рейтинг))
        conn.commit()
        conn.close()
        flash('Товар успешно добавлен!', 'success')
        return redirect(url_for('products'))
    
    return render_template('add_product.html')

# ==================== ЗАКАЗЫ ====================
@app.route('/orders')
def orders():
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT з.*, к.имя as клиент_имя, к.фамилия as клиент_фамилия,
               ку.имя as курьер_имя, ку.фамилия as курьер_фамилия
        FROM заказы з
        LEFT JOIN клиенты к ON з.клиент_id = к.id
        LEFT JOIN курьеры ку ON з.курьер_id = ку.id
        ORDER BY з.дата_заказа DESC
    ''').fetchall()
    conn.close()
    return render_template('orders.html', orders=orders)

@app.route('/add_order', methods=['GET', 'POST'])
def add_order():
    conn = get_db_connection()
    
    if request.method == 'POST':
        клиент_id = int(request.form['клиент_id'])
        курьер_id = int(request.form['курьер_id']) if request.form.get('курьер_id') else None
        сумма = float(request.form['сумма'])
        способ_оплаты = request.form.get('способ_оплаты', 'cash')
        статус = request.form.get('статус', 'pending')
        примечания = request.form.get('примечания', '')
        
        conn.execute('''
            INSERT INTO заказы (клиент_id, курьер_id, сумма, способ_оплаты, статус, примечания)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (клиент_id, курьер_id, сумма, способ_оплаты, статус, примечания))
        conn.commit()
        flash('Заказ успешно добавлен!', 'success')
        return redirect(url_for('orders'))
    
    # Получаем списки для выпадающих списков
    clients = conn.execute('SELECT id, имя, фамилия FROM клиенты').fetchall()
    couriers = conn.execute('SELECT id, имя, фамилия FROM курьеры WHERE статус = "active"').fetchall()
    conn.close()
    
    return render_template('add_order.html', clients=clients, couriers=couriers)

if __name__ == '__main__':
    app.run(debug=True)