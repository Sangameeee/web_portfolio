from flask import Flask, render_template, url_for, request, redirect, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, IntegerField, FormField, FieldList
from wtforms.validators import DataRequired, Email, NumberRange
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os
from dotenv import load_dotenv
#for timezone
import pytz
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import datetime, timedelta


class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Email()])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField("Submit")

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')




app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')  # Default database
app.config['SQLALCHEMY_BINDS'] = {
    'db2': os.getenv('DATABASE_URI_1')  # Second database
}

db = SQLAlchemy(app)

db2 = db

bcrypt = Bcrypt(app)

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    email = db.Column(db.String(250))
    message = db.Column(db.String(1000))



##timezone 
class Detail(db.Model):
    __bind_key__ = 'db2'
    __tablename__ = 'details'
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(50))
    office_hrs = db.Column(db.String(50))
    timezone_or = db.Column(db.String(50))
    UTC = db.Column(db.String(50))
    same_free_time = db.Column(db.String(100))

with app.app_context():
    db.create_all()

class PersonForm(FlaskForm):
    location = StringField('City or Country', validators=[DataRequired()])
    office_hours = StringField('Office Hours(e.g 9:00 - 17:00)', validators=[DataRequired()],
                               render_kw={"placeholder": "E.g., 9:00 - 17:00 "})
    class Meta:
        csrf = False

class DynamicForm(FlaskForm):
    numberofpeople = IntegerField('Numberofpeople', validators=[DataRequired(),
                                                                NumberRange(min=2,max=5,message="between 2 and 5")])
    submit_people = SubmitField('Submit People')
    people = FieldList(FormField(PersonForm), min_entries=0)
    submit_details = SubmitField('Submit details')
##end
# Admin credentials
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
ADMIN_PASSWORD_HASH = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')



##timezone function 
def delete_all():
    db.session.query(Detail).delete()
    db.session.commit()


def get_timezone(location):
    try:
        geolocator = Nominatim(user_agent="timezone_app")
        location_data = geolocator.geocode(location, timeout = 20)
        if not location_data:
            return None,f"Could not find location:{location}"
        
        latitude,longitude = location_data.latitude, location_data.longitude
        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
        if not timezone_str:
            return None,f"Timezone not found for location:{location}"
        timezone = pytz.timezone(timezone_str)
        utc_value = datetime.now(timezone).strftime('%z')

        return timezone_str, utc_value
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        return None,f"Geocoding Error: {str(e)}"
    except Exception as e:
        return None,f"Unexpected error: {str(e)}"
    
def time_to_utc(stime, utc_offset):
    time = datetime.strptime(stime, "%H:%M")
    sign = -1 if utc_offset[0] == "-" else 1
    hrs_offset = int(utc_offset[1:3])
    mins_offset = int(utc_offset[3:])

    offset = timedelta(hours=sign * hrs_offset, minutes=sign * mins_offset)

    utc_time = (time - offset).time()
    return utc_time.strftime("%H:%M")

def free_time(office_hrs):
    start_time_str, end_time_str = office_hrs.split(" - ")
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()

    day_start = datetime.strptime("00:00", "%H:%M").time()
    day_end = datetime.strptime("23:59", "%H:%M").time()
    free_times = []
    if start_time > day_start:
        free_times.append((day_start, start_time))
    if end_time < day_end:
        free_times.append((end_time, day_end))
    return free_times

def find_same_freetimes(total_free_times):
    same_times = total_free_times[0]
    for user_times in total_free_times[1:]:
        updated_mutual_times = []
        for start1, end1 in same_times:
            for start2, end2 in user_times:
                start_overlap = max(start1, start2)
                end_overlap = min(end1, end2)
                if start_overlap < end_overlap:
                    updated_mutual_times.append((start_overlap, end_overlap))
        same_times = updated_mutual_times
    return same_times

def utc_local(utc_range, timezone_str):
    timezone = pytz.timezone(timezone_str)
    today = datetime.now().date()

    start_utc = datetime.combine(today, utc_range[0])
    end_utc =  datetime.combine(today, utc_range[1])

    start_local = start_utc.astimezone(timezone)
    end_local = end_utc.astimezone(timezone)
    return start_local.strftime("%H:%M"), end_local.strftime("%H:%M")
##end

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/contactme', methods=['GET', 'POST'])
def contact_page():
    contact_form = ContactForm()
    if request.method == "POST" and contact_form.validate_on_submit():
        name = contact_form.name.data
        email = contact_form.email.data
        message = contact_form.message.data

        new_message = Message(name=name, email=email, message=message)
        db.session.add(new_message)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('contact.html', form=contact_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if username == ADMIN_USERNAME and bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_page'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/admin', methods=['GET'])
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    messages = Message.query.all()
    return render_template('admin.html', messages=messages)

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    message = Message.query.get(message_id)
    if message:
        db.session.delete(message)
        db.session.commit()
        flash('Message deleted successfully', 'success')
    else:
        flash('Message not found', 'error')
    return redirect(url_for('admin_page'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))


###timezone routes
@app.route('/timezone', methods=['GET', 'POST'])
def timezone_page():
    delete_all()
    form = DynamicForm()
    if request.method == 'POST':
        if 'submit_people' in request.form:
            form.people.entries = []
            for _ in range(form.numberofpeople.data):
                form.people.append_entry()
            
            with open("resultsfile.txt", "a") as file:
                file.write(f"Appended {form.numberofpeople.data} entries\n")
            
            return render_template('timezone.html', form=form)
        
        elif 'submit_details' in request.form:
            if not form.validate():
                return render_template('timezone.html', form=form)
            total_free_times = []
            for person_form in form.people:
                location = person_form.location.data
                office_hours = person_form.office_hours.data
                
                timezone_str, utc_value = get_timezone(location)
                start_time, end_time = office_hours.split(" - ")
                utc_format = time_to_utc(start_time, utc_value) + " - " + time_to_utc(end_time, utc_value)
                free_times = free_time(utc_format)
                total_free_times.append(free_times)
                
                if timezone_str is None:
                    person_form.location.errors.append(utc_value)
                    return render_template('timezone.html', form=form)
                
                new_message = Detail(
                    location=location,
                    office_hrs=office_hours,
                    timezone_or=timezone_str, 
                    UTC=utc_value
                )
                db.session.add(new_message)
            same_free_times = find_same_freetimes(total_free_times)
            for message in Detail.query.all():
                local_free_time = []
                for utc_range in same_free_times:
                    local_start, local_end = utc_local(utc_range, message.timezone_or)
                    local_free_time.append(f"{local_start} - {local_end}")
                message.same_free_time = ", ".join(local_free_time)

            db.session.commit()
            return redirect(url_for('result_page'))
    
    return render_template('timezone.html', form=form)

@app.route('/result')
def result_page():
    messages = Detail.query.all()
    return render_template('datasee.html',messages=messages)

###end 

if __name__ == "__main__":
    app.run(debug=True)
