from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling

# Secure hashed access code (plain: "letmein123")
ACCESS_CODE_HASH = hashlib.sha256("letmein123".encode()).hexdigest()


# ----------- Utility Functions -----------
def get_inventory():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory where quantity > 0 ORDER BY brand ASC"
    )
    data = cursor.fetchall()
    conn.close()
    return data


def is_logged_in():
    return session.get('logged_in', False)


# ----------- Routes -----------


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        input_code = request.form['access_code']
        hashed_input = hashlib.sha256(input_code.encode()).hexdigest()
        if hashed_input == ACCESS_CODE_HASH:
            session['logged_in'] = True
            return redirect(url_for('inventory_page'))
        else:
            return render_template('login.html', error='Invalid Access Code')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


import csv
import io


@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'csv_file' not in request.files:
        return "No file uploaded", 400

    file = request.files['csv_file']
    if file.filename == '':
        return "No selected file", 400

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)

        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()

        for row in csv_input:
            # Columns: brand, category, sku, mrp, finalsp, quantity
            cursor.execute(
                '''
                INSERT INTO inventory (brand, category, sku, mrp, finalsp, quantity)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                    brand = excluded.brand,
                    category = excluded.category,
                    mrp = excluded.mrp,
                    finalsp = excluded.finalsp,
                    quantity = inventory.quantity + excluded.quantity
            ''', (row['brand'], row['category'], row['sku'], float(
                    row['mrp']), float(row['finalsp']), int(row['quantity'])))

        conn.commit()
        conn.close()
        return redirect(url_for('manage_inventory'))

    except Exception as e:
        return f"Error processing CSV: {str(e)}", 500


@app.route('/')
def inventory_page():
    if not is_logged_in():
        return redirect(url_for('login'))

    products = get_inventory()
    cart = session.get('cart', {})
    return render_template('inventory.html', products=products, cart=cart)


from flask import Flask, render_template, request, redirect, url_for, session, flash


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if not is_logged_in():
        return redirect(url_for('login'))

    sku = request.form['sku']
    qty_str = request.form.get('qty')

    # Basic validation for quantity input
    if not qty_str or not qty_str.isdigit():
        flash("Please enter a valid quantity.", "danger")
        return redirect(url_for('inventory_page'))

    qty = int(qty_str)

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory WHERE sku = ?",
        (sku, ))
    item = cursor.fetchone()
    conn.close()

    if not item:
        flash("Invalid SKU.", "danger")
        return redirect(url_for('inventory_page'))

    available_stock = item[5]  # 'quantity' column from inventory table
    cart = session.get('cart', {})
    existing_qty = cart.get(sku, {}).get('qty', 0)

    if qty + existing_qty > available_stock:
        flash(f"Cannot add more than available stock ({available_stock}).",
              "danger")
        return redirect(url_for('inventory_page'))

    # Add to cart
    if sku in cart:
        cart[sku]['qty'] += qty
    else:
        cart[sku] = {
            'brand': item[0],
            'sku': item[2],
            'sp': item[4],
            'qty': qty
        }

    session['cart'] = cart
    flash("Item added to cart.", "success")
    return redirect(url_for('inventory_page'))


@app.route('/cart')
def view_cart():
    if not is_logged_in():
        return redirect(url_for('login'))

    cart = session.get('cart', {})
    grand_total = sum(item['sp'] * item['qty'] for item in cart.values())
    return render_template('cart.html', cart=cart, grand_total=grand_total)


@app.route('/remove_from_cart/<sku>')
def remove_from_cart(sku):
    if not is_logged_in():
        return redirect(url_for('login'))

    cart = session.get('cart', {})
    if sku in cart:
        del cart[sku]
    session['cart'] = cart
    return redirect(url_for('view_cart'))


@app.route('/manage', methods=['GET', 'POST'])
def manage_inventory():
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add-new':
            try:
                cursor.execute(
                    '''
                    INSERT INTO inventory (brand, category, sku, mrp, finalsp, quantity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (request.form['brand'], request.form['category'],
                      request.form['sku'], float(request.form['mrp']),
                      float(request.form['sp']), int(request.form['qty'])))
                conn.commit()
            except Exception as e:
                print("Error adding SKU:", e)
        elif action == 'update-existing':
            try:
                cursor.execute(
                    '''
                    UPDATE inventory
                    SET quantity = quantity + ?
                    WHERE brand = ? AND sku = ?
                ''',
                    (int(request.form['update_qty']),
                     request.form['update_brand'], request.form['update_sku']))
                conn.commit()
            except Exception as e:
                print("Error updating quantity:", e)

    cursor.execute("SELECT brand, sku FROM inventory")
    brand_sku_data = cursor.fetchall()
    brand_sku_map = {}
    for brand, sku in brand_sku_data:
        brand_sku_map.setdefault(brand, []).append(sku)
    brands = sorted(brand_sku_map.keys())

    cursor.execute(
        "SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory ORDER BY quantity ASC"
    )
    inventory_data = cursor.fetchall()

    conn.close()

    return render_template('manage.html',
                           brands=brands,
                           brand_sku_map=brand_sku_map,
                           inventory_data=inventory_data)


@app.route('/orders')
def view_orders():
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT customer_name, mobile, sku, sp, quantity, total, timestamp, payment_mode
        FROM orders ORDER BY timestamp DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    grouped_orders = {}
    for row in rows:
        key = f"{row[0]} | {row[1]}"
        if key not in grouped_orders:
            grouped_orders[key] = {"orders": [], "grand_total": 0}
        grouped_orders[key]["orders"].append({
            "sku": row[2],
            "sp": row[3],
            "qty": row[4],
            "total": row[5],
            "timestamp": row[6],
            "payment_mode": row[7]
        })
        grouped_orders[key]["grand_total"] += row[5]

    return render_template('orders.html', grouped_orders=grouped_orders)


@app.route('/submit_order', methods=['POST'])
def submit_order():
    if not is_logged_in():
        return redirect(url_for('login'))

    name = request.form['name']
    mobile = request.form['mobile']
    payment = request.form['payment']
    cart = session.get('cart', {})

    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for sku, item in cart.items():
        qty = item['qty']
        sp = item['sp']
        total = qty * sp

        cursor.execute(
            '''
            INSERT INTO orders (timestamp, customer_name, mobile, sku, sp, quantity, total, payment_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, name, mobile, sku, sp, qty, total, payment))

        cursor.execute(
            '''
            UPDATE inventory SET quantity = quantity - ? WHERE sku = ?
        ''', (qty, sku))

    conn.commit()
    conn.close()
    session.pop('cart', None)
    return redirect(url_for('inventory_page'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
