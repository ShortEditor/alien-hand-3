from flask import Flask, render_template, request, send_file, session
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
import json
from io import BytesIO
from datetime import datetime, timedelta
import requests

app = Flask(__name__)
app.secret_key = 'alien_hand_3_secret_key'

# Global variables
current_ticket_number = 100

# Telegram configuration
TELEGRAM_BOT_TOKEN = '7848973864:AAHl5y2gDQKsTz4ibjCk_EtUfAimGyOG9ME'
TELEGRAM_CHAT_ID = '5518104198'

def load_bookings():
    try:
        with open('bookings.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def save_bookings(bookings):
    with open('bookings.json', 'w') as f:
        json.dump(bookings, f)

def send_telegram_notification(name, email, phone, num_tickets, ticket_numbers, amount):
    try:
        message = f"""
🎫 New Ticket Booking!

👤 Customer Details:
- Name: {name}
- Email: {email}
- Phone: {phone}

🎟️ Booking Details:
- Number of Tickets: {num_tickets}
- Ticket Numbers: {', '.join(map(str, ticket_numbers))}
- Total Amount: ₹{amount}

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data)
        print("Telegram notification sent successfully")
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/select-show')
def select_show():
    # Generate dates for next 3 days
    dates = []
    for i in range(3):
        date = datetime.now() + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    return render_template('select_show.html', dates=dates)

@app.route('/book-tickets')
def book_tickets():
    return render_template('index.html')

@app.route('/reset_tickets')
def reset_tickets():
    global current_ticket_number
    current_ticket_number = 100
    return "Ticket numbers reset to 100"

@app.route('/book', methods=['POST'])
def book():
    global current_ticket_number
    
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    num_tickets = int(request.form['num_tickets'])
    
    # Generate ticket numbers in decreasing order
    ticket_numbers = list(range(current_ticket_number, current_ticket_number - num_tickets, -1))
    current_ticket_number -= num_tickets
    
    # Create payment QR code
    amount = num_tickets * 100  # Changed ticket cost from 200 to 100
    upi_payment_string = f"upi://pay?pa=9160068402@ybl&pn=MovieTickets&am={amount}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_payment_string)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code
    if not os.path.exists('static'):
        os.makedirs('static')
    qr_path = f"static/qr_{email}.png"
    qr_img.save(qr_path)
    
    # Store booking details
    bookings = load_bookings()
    bookings[email] = {
        'name': name,
        'phone': phone,
        'num_tickets': num_tickets,
        'ticket_numbers': ticket_numbers,
        'amount': amount,
        'paid': False,
        'movie': 'Alien Hand 3'
    }
    save_bookings(bookings)
    
    # Send Telegram notification
    send_telegram_notification(name, email, phone, num_tickets, ticket_numbers, amount)
    
    return render_template('payment.html', 
                         qr_path=qr_path, 
                         amount=amount,
                         email=email,
                         name=name,
                         phone=phone,
                         ticket_numbers=ticket_numbers)

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    email = request.form['email']
    transaction_id = request.form['transaction_id']
    
    # Load booking details
    bookings = load_bookings()
    booking = bookings.get(email, {})
    name = booking.get('name', 'Guest')
    phone = booking.get('phone', '')
    ticket_numbers = booking.get('ticket_numbers', [])
    amount = booking.get('amount', 100)
    
    # Generate PDF ticket
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    
    # Set font for the entire document
    c.setFont("Helvetica-Bold", 24)
    
    # Add header
    c.drawString(width/2 - 80, height - 50, "ALIEN HAND 3")
    c.setFont("Helvetica", 12)
    c.drawString(width/2 - 80, height - 70, "Superhero | Mystical | Action")
    
    # Add horizontal lines
    c.setStrokeColor(colors.grey)
    c.line(50, height - 80, width - 50, height - 80)
    
    # Add QR Code for ticket verification
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(f"TICKET-{transaction_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img_path = f"static/ticket_qr_{email}.png"
    qr_img.save(qr_img_path)
    c.drawImage(qr_img_path, width - 100, height - 150, width=80, height=80)
    
    # Add ticket information with better formatting
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 150, "TICKET DETAILS")
    c.setFont("Helvetica", 12)
    
    # Left column information
    y_pos = height - 180
    details = [
        ("Booking ID", f"{transaction_id[:8].upper()}"),
        ("Show Date", datetime.now().strftime('%d %b %Y')),
        ("Show Time", "7:30 PM"),
        ("Seat Type", "PREMIUM"),
        ("Amount Paid", f"₹{amount}"),
        ("Ticket Numbers", ", ".join(map(str, ticket_numbers)))
    ]
    
    for label, value in details:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y_pos, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(150, y_pos, value)
        y_pos -= 20
    
    # Customer Information
    y_pos -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_pos, "CUSTOMER INFORMATION")
    c.setFont("Helvetica", 10)
    
    y_pos -= 30
    customer_details = [
        ("Name", name),
        ("Email", email),
        ("Phone", phone)
    ]
    
    for label, value in customer_details:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y_pos, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(150, y_pos, value)
        y_pos -= 20
    
    # Venue Information
    y_pos -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_pos, "VENUE")
    c.setFont("Helvetica", 10)
    
    y_pos -= 30
    venue_details = [
        "Aliens Theatre",
        "Junction Road",
        "Rajahmundry, Andhra Pradesh"
    ]
    
    for line in venue_details:
        c.drawString(50, y_pos, line)
        y_pos -= 20
    
    # Terms and Conditions
    y_pos -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, "Terms & Conditions:")
    c.setFont("Helvetica", 8)
    
    y_pos -= 20
    terms = [
        "1. Please arrive 30 minutes before show time",
        "2. Outside food and beverages are not allowed",
        "3. Please keep this ticket handy for verification",
        "4. Ticket is valid only for the specified show time and date"
    ]
    
    for term in terms:
        c.drawString(50, y_pos, term)
        y_pos -= 15
    
    # Bottom border and movie info
    c.setStrokeColor(colors.grey)
    c.line(50, 80, width - 50, 80)
    c.setFont("Helvetica", 10)
    c.drawString(50, 60, "Rating: UA | Duration: 1h | Language: Telugu")
    c.drawString(width - 250, 60, "Instagram: @bhargav_works")
    
    c.save()
    
    # Clean up temporary QR code file
    os.remove(qr_img_path)
    
    # Move buffer position to beginning
    pdf_buffer.seek(0)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f'alien_hand_3_ticket_{transaction_id[:8]}.pdf',
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)
