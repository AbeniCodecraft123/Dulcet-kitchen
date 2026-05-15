import os
from dotenv import load_dotenv

load_dotenv()
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField, TimeField, DateField, TextAreaField
from wtforms.fields.numeric import IntegerField
from wtforms.validators import DataRequired, Email
from flask_mail import Mail, Message
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.google import google
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'abenicodecraft001@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_ROUTE')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = f"{os.getenv('APP_SECRET_KEY')}"
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    scope=[
        "openid",
        f"{os.getenv('GO_ROUTE')}",
        f"{os.getenv('GOO_ROUTE')}",
    ],
    redirect_to="google_login"   # endpoint name
)

app.register_blueprint(google_bp, url_prefix="/login")

db = SQLAlchemy(app)
mail = Mail(app)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')

    def __init__(self, name, email, phone, date, time, guests):
        self.name = name
        self.email = email
        self.phone = phone
        self.date = date
        self.time = time
        self.guests = guests

    def __repr__(self):
        return f"<Reservation {self.name} - {self.date} {self.time}>"


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    image = db.Column(db.String(300))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')

    def __init__(self, name, email, image, message):
        self.name = name
        self.email = email
        self.image = image
        self.message = message

    def __repr__(self):
        return f"<Review {self.name}>"



class ReservationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    time = TimeField('Time', validators=[DataRequired()])
    guests = IntegerField('Guests', validators=[DataRequired()])
    submit = SubmitField('Book Table')


class ReviewForm(FlaskForm):
    message = TextAreaField('Your Review', validators=[DataRequired()])
    submit = SubmitField('Submit Review')



@app.route('/', methods=['GET', 'POST'])
def index():
    reservation_form = ReservationForm()
    review_form = ReviewForm()

    approved_reviews = Review.query.filter_by(status='approved').all()

    return render_template(
        'index.html',
        reservation_form=reservation_form,
        review_form=review_form,
        reviews=approved_reviews
    )


@app.route('/admin/dashboard')
def admin_dashboard():
    reservations = Reservation.query.order_by(Reservation.id.desc()).all()
    pending_reviews = Review.query.filter_by(status='pending').all()
    approved_reviews = Review.query.filter_by(status='approved').all()

    return render_template(
        'admin_dashboard.html',
        reservations=reservations,
        pending_reviews=pending_reviews,
        approved_reviews=approved_reviews
    )

@app.route('/reserve', methods=['POST'])
def reserve():
    form = ReservationForm()

    if form.validate_on_submit():
        reservation = Reservation(
            form.name.data,
            form.email.data,
            form.phone.data,
            str(form.date.data),
            str(form.time.data),
            form.guests.data
        )

        db.session.add(reservation)
        db.session.commit()

        flash("Your reservation has been received. Our team will contact you shortly via email to confirm availability.",
              "reservation_success")
        return redirect('/')




# Google login callback
@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        user_info = resp.json()
        # Store user info in session for review submissions
        session['user'] = {
            "name": f"{user_info.get('given_name')} {user_info.get('family_name')}",
            "email": user_info["email"],
            "picture": user_info.get("picture")
        }
        flash(f"Logged in as {session['user']['name']}", "success")
    else:
        flash("Failed to fetch Google account info.", "danger")

    return redirect(url_for('index'))

@app.route('/login/google')
def login_google():
    session['user'] = {
        "name": "Test User",
        "email": "test@gmail.com",
        "picture": "https://via.placeholder.com/50"
    }
    return redirect('/')


@app.route('/add_review', methods=['GET', 'POST'])
def add_review():
    form = ReviewForm()
    user = session.get('user')

    if not user:
        flash("Please log in with Google to submit a review.", "warning")
        return redirect(url_for("google.login"))

    if request.method == 'POST' and form.validate_on_submit():
        review = Review(
            name=user['name'],
            email=user['email'],
            image=user['picture'],
            message=form.message.data
        )
        db.session.add(review)
        db.session.commit()
        flash("Thank you for sharing your experience with Dulcet Kitchen.", "review_success")
        return redirect(url_for('index'))
    return render_template("review_form.html", form=form)


@app.route('/admin/reviews')
def admin_reviews():
    reviews = Review.query.filter_by(status='pending').all()
    return render_template('admin_reviews.html', reviews=reviews)


@app.route('/approve_review/<int:id>')
def approve_review(id):
    review = Review.query.get(id)
    review.status = 'approved'
    db.session.commit()
    flash(f"Review by {review.name} approved!", "success")
    return redirect('/admin/dashboard')

@app.route('/delete_review/<int:id>')
def delete_review(id):
    review = Review.query.get(id)
    db.session.delete(review)
    db.session.commit()
    flash("Review deleted successfully!", "info")
    return redirect('/admin/dashboard')

@app.route('/approve_reservation/<int:id>')
def approve_reservation(id):
    reservation = Reservation.query.get(id)

    reservation.status = 'approved'
    db.session.commit()

    # 📧 APPROVAL EMAIL
    msg = Message(
        subject="Reservation Approved - Dulcet Restaurant",
        sender=app.config['MAIL_USERNAME'],
        recipients=[reservation.email]
    )

    msg.body = f"""
Hello {reservation.name},

Good news! 🎉

Your reservation for {reservation.date} at {reservation.time} has been APPROVED.

A table has been reserved for you and your guest(s).

We look forward to serving you!

Best regards,
Dulcet Restaurant Team
    """

    mail.send(msg)

    return redirect('/admin/dashboard')

@app.route('/reject_reservation/<int:id>')
def reject_reservation(id):
    reservation = Reservation.query.get(id)

    reservation.status = 'rejected'
    db.session.commit()

    # 📧 REJECTION EMAIL
    msg = Message(
        subject="Reservation Update - Dulcet Restaurant",
        sender=app.config['MAIL_USERNAME'],
        recipients=[reservation.email]
    )

    msg.body = f"""
Hello {reservation.name},

We sincerely appreciate your interest in Dulcet Restaurant.

Unfortunately, we regret to inform you that we are fully booked for {reservation.date} at {reservation.time}.

We truly apologize for any inconvenience caused.

If any space becomes available before your selected date, we will notify you via email immediately.

Thank you for your understanding.

Warm regards,
Dulcet Restaurant Team
    """

    mail.send(msg)

    return redirect('/admin/dashboard')



@app.route('/admin/reservations')
def admin_reservations():
    reservations = Reservation.query.all()
    return render_template('admin_reservations.html', reservations=reservations)



with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')