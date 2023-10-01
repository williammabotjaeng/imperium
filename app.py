from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf import FlaskForm
from flask_mail import Message, Mail
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField, FloatField, IntegerField, FileField
from wtforms.validators import InputRequired, Length, DataRequired, Email, URL
from dotenv import load_dotenv
from datetime import datetime
from bitcoinlib.wallets import Wallet
from web3 import Web3
from solcx import compile_standard
from base64 import b64encode

import moment
import requests
import os
import json 

app = Flask(__name__)

load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'QPEunVzlmptwr73MfPz44w=='
api_token = os.getenv("API_TOKEN")
log_config_id = os.getenv("CONFIG_ID")

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")  
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD") 
app.config["INFURA_PROJECT_ID"] = os.getenv("INFURA_PROJECT_ID") 

infura_id = app.config["INFURA_PROJECT_ID"]

web3 = Web3(Web3.HTTPProvider(f"https://ropsten.infura.io/v3/{infura_id}"))

with open('imperium_contract.sol', 'r') as f:
    contract_code = f.read()

compiled_sol = compile_standard({
    "language": "Solidity",
    "sources": {
        "imperium_contract.sol": {
            "content": contract_code
        }
    },
    "settings": {
        "outputSelection": {
            "*": {
                "*": ["abi", "evm.bytecode"]
            }
        }
    }
})

contract_abi = compiled_sol['contracts']['imperium_contract.sol']['Imperium']['abi']
contract_bytecode = compiled_sol['contracts']['imperium_contract.sol']['Imperium']['evm']['bytecode']['object']

contract_data = {
    'abi': contract_abi,
    'bytecode': contract_bytecode
}

with open('contract.json', 'w') as f:
    json.dump(contract_data, f)

mail = Mail(app)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=True)
    address_line1 = db.Column(db.String(100), unique=True, nullable=True)
    address_line2 = db.Column(db.String(100), unique=True, nullable=True)
    city = db.Column(db.String(100), unique=True, nullable=True)
    postal_code = db.Column(db.String(100), unique=True, nullable=True)
    mobile_no = db.Column(db.String(100), unique=True, nullable=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.String(100), nullable=True)
    wallet_address = db.Column(db.String(100), unique=True, nullable=True)
    wallet_name = db.Column(db.String(100), unique=True, nullable=True)
    primary_network = db.Column(db.String(500), nullable=True)
    primary_account = db.Column(db.String(500), nullable=True)
    master_key = db.Column(db.String(500), unique=True, nullable=True)
    voting_power = db.Column(db.Integer, default=0, nullable=True)
    user_votes = db.relationship('Vote', backref='user', lazy=True)
    projects = db.relationship('Project', backref='user', lazy=True)
    transactions = db.Column(db.PickleType, nullable=True)  
    accounts = db.Column(db.PickleType, nullable=True)  
    assets_for_sale = db.Column(db.PickleType, nullable=True)  

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    funding_goal = db.Column(db.Float, nullable=False)
    current_funding = db.Column(db.Float, nullable=False)
    vote_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    logo_image = db.Column(db.LargeBinary, nullable=True) 
    youtube_video_link = db.Column(db.String(100), nullable=True)

    project_votes = db.relationship('Vote', backref='project', lazy=True)

    def __repr__(self):
        return f"Project('{self.title}', '{self.description}')"

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    preference = db.Column(db.String(50), nullable=False)

    project_vote = db.relationship('Project', backref='votes', lazy=True)

    def __repr__(self):
        return f"Vote('{self.project_id}', '{self.user_id}', '{self.preference}')"


class Price(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cryptocurrency = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Price('{self.cryptocurrency}', '{self.price}', '{self.timestamp}')"

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(100))
    actor = db.Column(db.String(100))
    action = db.Column(db.String(100))
    target = db.Column(db.String(100))
    status = db.Column(db.String(100))
    request_time = db.Column(db.String(100))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Length(min=4, max=100)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=64)])

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Length(min=4, max=100)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=64)])

class ContactForm(FlaskForm):
    contact_type = SelectField('Contact Type',validators=[InputRequired()], choices=[('Customer', 'Customer'), ('Supplier', 'Supplier')])
    first_name = StringField('First Name', validators=[InputRequired(), Length(min=2, max=100)])
    last_name = StringField('Last Name',  validators=[Length(min=2, max=100)])
    email = StringField('Email', validators=[InputRequired(), Length(min=6, max=100)])
    phone_number = StringField('Phone Number')
    address = StringField('Address')
    status = StringField('Status')
    ip_address = StringField('IP Address', validators=[InputRequired()])
    submit = SubmitField('Create Contact')
class ContactUsForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    message = TextAreaField("Message", validators=[DataRequired()])
    submit = SubmitField("Send")

class ProjectForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    funding_goal = FloatField('Funding Goal', validators=[DataRequired()])
    current_funding = FloatField('Current Funding', default=0)
    user_id = IntegerField('User ID')
    logo_image = FileField('Logo Image')
    youtube_video_link = StringField('YouTube Video Link', validators=[URL()])

class SettingsForm(FlaskForm):
    username = StringField('Username', validators=[Length(max=20)])
    address_line1 = StringField('Address Line 1')
    address_line2 = StringField('Address Line 2')
    city = StringField('City')
    postal_code = StringField('Postal/Zip Code')
    mobile_no = StringField('Mobile No.')

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    return render_template("index.html", form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data

            user = User.query.filter_by(email=email).first()
            
            if not user or not check_password_hash(user.password, password):
                flash('Please check your login details and try again.')
                return redirect(url_for('login'))

            login_user(user)
            return redirect(url_for('home'))

    return render_template("login.html", form=form)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
   
    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data

            user = User.query.filter_by(email=email).first()
            if user:
                flash('Username already exists. Please choose a different one.')
                return redirect(url_for('login'))

            new_user = User(email=email, password=generate_password_hash(password, method='sha256'), voting_power=1)
            db.session.add(new_user)
            db.session.commit()
          
            # Send email to the new user
            msg = Message(
                subject="Welcome to Imperium!",
                sender=app.config["MAIL_USERNAME"],
                recipients=[email],
                body=f"Hi {email},\n\nThank you for registering on our website. We are excited to have you as a member!\n\nBest regards,\Imperium Team"
            )
            mail.send(msg)

            flash('Registration successful! An email has been sent to your email address.')
            user = User.query.filter_by(email=email).first()
            login_user(user)
            print("User Created")
            return redirect(url_for('home'))
    return render_template("register.html", form=form)

@app.route("/home")
def home():
    settings_form = SettingsForm()
    projects = Project.query.all()  
    print(projects)
    users = User.query.filter(User.id != current_user.id).filter(User.username.isnot(None)).all()
    return render_template("home.html", projects=projects, users=users, settings_form=settings_form, b64encode=b64encode)

@app.route('/settings', methods=['POST'])
@login_required
def settings():
    form = SettingsForm(request.form)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.address_line1 = form.address_line1.data
        current_user.address_line2 = form.address_line2.data
        current_user.city = form.city.data
        current_user.postal_code = form.postal_code.data
        current_user.mobile_no = form.mobile_no.data
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('home'))
    


@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    form = ProjectForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            # Process the form data and create a new project
            title = form.title.data
            description = form.description.data
            funding_goal = form.funding_goal.data
            current_funding = form.current_funding.data
            image_file = request.files['logo_image']
            youtube_video_link = form.youtube_video_link.data

            image_data = image_file.read()

            # Create a new Project object
            project = Project(
                title=title,
                description=description,
                funding_goal=funding_goal,
                current_funding=current_funding,
                user_id=current_user.id,
                logo_image=image_data,
                youtube_video_link=youtube_video_link
            )

            # Save the project to the database
            db.session.add(project)
            db.session.commit()
            print("Saved to Database")

            # Redirect to a success page or another route
            return redirect(url_for('home'))

    return render_template('create_project.html', form=form)

@app.route('/project/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    form = ProjectForm()
    project = Project.query.get(project_id)

    if project:
        return render_template('project.html', project=project, form=form)
    else:
        return 'Project not found', 404
    
@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get(project_id)

    if not project:
        return 'Project not found', 404

    form = ProjectForm()

    if form.validate_on_submit():
        project.title = form.title.data
        project.description = form.description.data
        project.funding_goal = form.funding_goal.data
        project.current_funding = form.current_funding.data
        project.youtube_video_link = form.youtube_video_link.data

        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('projects'))

    elif request.method == 'GET':
        form.title.data = project.title
        form.description.data = project.description
        form.funding_goal.data = project.funding_goal
        form.current_funding.data = project.current_funding
        form.youtube_video_link.data = project.youtube_video_link

    return render_template('edit_project.html', project=project, form=form)

@app.route('/vote_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def vote_project(project_id):
    form = ProjectForm()
    project = Project.query.get(project_id)

    if not project:
        return 'Project not found', 404

    if current_user.voting_power:
        # Decrease the current user's voting power
        current_user.voting_power -= 1

        # Increase the number of project votes
        project.vote_count += 1

        # Create a Vote object and save it to the database
        vote = Vote(project_id=project.id, user_id=current_user.id, preference=project.id)
        db.session.add(vote)

        db.session.commit()
        flash('Vote submitted successfully!', 'success')
        return redirect(url_for('projects', project_id=project.id))# Set a default preference value

    return render_template('vote_project.html', project=project, form=form)
    
@app.route("/projects", methods=['GET'])
@login_required 
def projects():
    projects = Project.query.all()
    return render_template('projects.html', projects=projects)
    
@app.route("/create_wallet", methods=['GET', 'POST'])
@login_required 
def create_wallet():
    if current_user.wallet_address:
        return redirect(url_for('home')) 

    # Generate wallet and get the address
    wallet_name = f"ImperiumKibisis23100{current_user.id}"
    wallet = Wallet.create(wallet_name)
    wallet_address = wallet.get_key().address

    # Save the wallet address to the current user's database record
    current_user.wallet_address = wallet_address
    current_user.wallet_name = wallet_name
    current_user.balance = wallet.balance(as_string=True)
    current_user.primary_network = wallet.network_list()[0]
    current_user.primary_account = wallet.accounts()[0]
    current_user.master_key = str(wallet.public_master().wif)
    current_user.transactions = wallet.transactions()
    current_user.accounts = wallet.accounts()
    
    db.session.commit()

    return redirect(url_for('home')) 

@app.route("/what")
def what():
    return render_template("what.html")

@app.route("/getintouch", methods=["GET", "POST"])
def contact():
    form = ContactUsForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        message = form.message.data

        msg = Message(
            subject="New Message from Contact Form",
            sender=app.config["MAIL_USERNAME"],
            recipients=[app.config["MAIL_USERNAME"]],
            body=f"Name: {name}\nEmail: {email}\nMessage: {message}"
        )

        mail.send(msg)

        flash("Your message has been sent successfully!", "success")
        return redirect(url_for("home"))

    return render_template("getintouch.html", form=form, current_user=current_user)

# @app.route("/contacts")
# @login_required
# def contacts():
#     contacts = Contact.query.filter_by(user_id=current_user.id).all()
#     return render_template("contacts.html", current_user=current_user, contacts=contacts)

import requests

# @app.route("/create_contact", methods=["GET", "POST"])
# @login_required
# def create_contact():
#     print("Config ID", log_config_id)
#     print("API Token", api_token)
#     if request.method == "POST":
#         contact_type = request.form.get("contact_type")
#         first_name = request.form.get("first_name")
#         email = request.form.get("email")
#         ip_address = request.form.get("ip_address")

#         new_contact = Contact(
#             contact_type=contact_type,
#             first_name=first_name,
#             email=email,
#             ip_address=ip_address,
#             user_id=current_user.id  
#         )

#         db.session.add(new_contact)
#         db.session.commit()
        
#         # Log the contact creation event
#         log_data = {
#             "config_id": f"{log_config_id}",
#             'event': {
#                 'message': 'Creating Contact'
#             }
#         }
#         headers = {
#             'Authorization': f"Bearer {api_token}",
#             'Content-Type': 'application/json'
#         }
        
#         response = requests.post('https://audit.aws.eu.pangea.cloud/v1/log', json=log_data, headers=headers)
#         res = response.json()
#         # Save the log data to the database
#         log = Log(
#             message=log_data['event']['message'],
#             actor=current_user.id,
#             action='create',
#             target='Contact',
#             status='success',
#             request_time=res['request_time']
#         )
#         db.session.add(log)
#         db.session.commit()

#         return redirect(url_for("contacts"))
    
#     return render_template("create_contact.html", current_user=current_user)

# @app.route("/contacts/delete/<int:contact_id>", methods=["POST"])
# @login_required
# def delete_contact(contact_id):
#     app.logger.info('Deleting contact with ID: %s', contact_id)

#     contact = Contact.query.filter_by(user_id=current_user.id, id=contact_id).first()
#     if contact:
#         app.logger.info('Contact found. Deleting contact: %s', contact)
#         db.session.delete(contact)
#         db.session.commit()
#     else:
#         app.logger.warning('Contact not found with ID: %s', contact_id)

#     # Log the contact deletion event
#     log_data = {
#         "config_id": f"{log_config_id}",
#         'event': {
#             'message': 'Deleting contact'
#         }
#     }
#     headers = {
#         'Authorization': f"Bearer {api_token}",
#         'Content-Type': 'application/json'
#     }

#     response = requests.post('https://audit.aws.eu.pangea.cloud/v1/log', json=log_data, headers=headers)
#     res = response.json()

#     # Save the log data to the database
#     log = Log(
#         message=log_data['event']['message'],
#         actor=current_user.id,
#         action='delete',
#         target='Contact',
#         status='success',
#         request_time=res['request_time']
#     )
#     db.session.add(log)
#     db.session.commit()

#     app.logger.info('Contact deletion completed')
#     return redirect(url_for("contacts"))

# @app.route("/contacts/edit/<int:contact_id>", methods=["GET", "POST"])
# @login_required
# def edit_contact(contact_id):
#     contact = Contact.query.filter_by(user_id=current_user.id, id=contact_id).first()
#     print("Contact: ", contact)
#     if not contact:
#         return redirect(url_for("contacts"))

#     if request.method == "POST":
#         # Update the contact object with the new data from the form
#         print(request.form)
#         contact.first_name = request.form.get("first_name")
#         contact.last_name = request.form.get("last_name")
#         contact.email = request.form.get("email")
#         contact.phone_number = request.form.get("phone_number")
#         contact.address = request.form.get("address")
#         contact.status = request.form.get("status")
#         contact.ip_address = request.form.get("ip_address")
#         db.session.commit()

#         # Log the contact update event
#         log_data = {
#             "config_id": f"{log_config_id}",
#             'event': {
#                 'message': 'Updating Contact'
#             }
#         }
#         headers = {
#             'Authorization': f"Bearer {api_token}",
#             'Content-Type': 'application/json'
#         }

#         response = requests.post('https://audit.aws.eu.pangea.cloud/v1/log', json=log_data, headers=headers)
#         res = response.json()

#         # Save the log data to the database
#         log = Log(
#             message=log_data['event']['message'],
#             actor=current_user.id,
#             action='update',
#             target='Contact',
#             status='success',
#             request_time=res['request_time']
#         )
#         db.session.add(log)
#         db.session.commit()

#         print("Done, Saved Data!")
#         return redirect(url_for("contacts"))
#     else:
#         return render_template("edit_contact.html", current_user=current_user, contact=contact)

@app.route("/logs")
@login_required
def logs():
    user_id = current_user.id

    # Retrieve logs from the database with the current_user's id as the actor field
    logs = Log.query.filter_by(actor=user_id).all()
    for log in logs:
        print(log.request_time)

    return render_template("logs.html", logs=logs, moment=moment, datetime=datetime)

# @app.route("/get_contact", methods=["GET", "POST"])
# @login_required
# def get_contact():
#     if request.method == "POST":
#         email = request.form.get("email")
#         contact = Contact.query.filter_by(email=email).first()

#         if contact:
#             # Contact found, do something with it
#             return render_template("contact_details.html", contact=contact)
#         else:
#             # Contact not found
#             return render_template("contact_not_found.html")
    
#     return render_template("get_contact.html", current_user=current_user)

@app.route("/docs")
def docs():
    return render_template("docs.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
