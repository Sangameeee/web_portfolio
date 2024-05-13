from flask import Flask, render_template, url_for
from flask_wtf import FlaskForm
from wtforms import StringField,SubmitField,TextAreaField
from wtforms.validators import DataRequired 

class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email')
    message = TextAreaField('Message', validators=[DataRequired()])
    submit  = SubmitField("Submit")

app = Flask(__name__)
app.secret_key = "dontbelikethat"


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/contactme')
def contact_page():
    contact_form = ContactForm()
    contact_form.validate_on_submit()
    return render_template('contact.html', form=contact_form) 



if __name__ == "__main__":
    app.run(debug=True)

