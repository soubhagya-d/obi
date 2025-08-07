from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # needed for session

def get_inventory():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory")
    data = cursor.fetchall()
    conn.close()
    return data

@app.route('/')
def inventory_page():
    products = get_inventory()
    cart = session.get('cart', {})
    return render_template('inventory.html', products=products, cart=cart)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    sku = request.form['sku']
    qty = int(request.form['qty'])

    # Load product from DB
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory WHERE sku = ?", (sku,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        return "Invalid SKU", 400

    cart = session.get('cart', {})

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
    return redirect(url_for('inventory_page'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    grand_total = sum(item['sp'] * item['qty'] for item in cart.values())
    return render_template('cart.html', cart=cart, grand_total=grand_total)

@app.route('/remove_from_cart/<sku>')
def remove_from_cart(sku):
    cart = session.get('cart', {})
    if sku in cart:
        del cart[sku]
    session['cart'] = cart
    return redirect(url_for('view_cart'))


@app.route('/manage', methods=['GET', 'POST'])
def manage_inventory():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Handle Form Submission
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add-new':
            try:
                cursor.execute('''
                    INSERT INTO inventory (brand, category, sku, mrp, finalsp, quantity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    request.form['brand'],
                    request.form['category'],
                    request.form['sku'],
                    float(request.form['mrp']),
                    float(request.form['sp']),
                    int(request.form['qty'])
                ))
                conn.commit()
            except Exception as e:
                print("Error adding SKU:", e)

        elif action == 'update-existing':
            try:
                cursor.execute('''
                    UPDATE inventory
                    SET quantity = quantity + ?
                    WHERE brand = ? AND sku = ?
                ''', (
                    int(request.form['update_qty']),
                    request.form['update_brand'],
                    request.form['update_sku']
                ))
                conn.commit()
            except Exception as e:
                print("Error updating quantity:", e)

    # Get all brands and their SKUs for dropdown
    cursor.execute("SELECT brand, sku FROM inventory")
    brand_sku_data = cursor.fetchall()
    brand_sku_map = {}
    for brand, sku in brand_sku_data:
        brand_sku_map.setdefault(brand, []).append(sku)
    brands = sorted(brand_sku_map.keys())

    # Get full inventory table
    cursor.execute("SELECT brand, category, sku, mrp, finalsp, quantity FROM inventory ORDER BY brand, sku")
    inventory_data = cursor.fetchall()

    conn.close()

    return render_template(
        'manage.html',
        brands=brands,
        brand_sku_map=brand_sku_map,
        inventory_data=inventory_data
    )




@app.route('/orders')
def view_orders():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT customer_name, mobile, sku, sp, quantity, total, timestamp, payment_mode
        FROM orders
        ORDER BY timestamp DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()

    # Group orders by customer (name + mobile)
    grouped_orders = {}
    for row in rows:
        key = f"{row[0]} | {row[1]}"
        if key not in grouped_orders:
            grouped_orders[key] = {
                "orders": [],
                "grand_total": 0
            }
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

        # Insert order
        cursor.execute('''
            INSERT INTO orders (timestamp, customer_name, mobile, sku, sp, quantity, total, payment_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, name, mobile, sku, sp, qty, total, payment))

        # Update inventory
        cursor.execute('''
            UPDATE inventory SET quantity = quantity - ? WHERE sku = ?
        ''', (qty, sku))

    conn.commit()
    conn.close()

    session.pop('cart', None)
    return redirect(url_for('inventory_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
