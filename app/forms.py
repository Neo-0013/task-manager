from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateTimeField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models import User

class RegistrationForm(FlaskForm):
    """User registration form"""
    username = StringField('Username', 
                          validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', 
                       validators=[DataRequired(), Email()])
    password = PasswordField('Password', 
                            validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')
    
    def validate_username(self, username):
        """Check if username already exists"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose another.')
    
    def validate_email(self, email):
        """Check if email already exists"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')


class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


class TaskForm(FlaskForm):
    """Task creation/editing form"""
    title = StringField('Task Title', 
                       validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', 
                               validators=[Optional(), Length(max=1000)])
    priority = SelectField('Priority', 
                          choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')],
                          coerce=int,
                          default=2)
    category = StringField('Category', 
                          validators=[Optional(), Length(max=50)])
    due_date = DateTimeField('Due Date (Optional)', 
                            format='%Y-%m-%d %H:%M',
                            validators=[Optional()])
    status = SelectField('Status',
                        choices=[('pending', 'Pending'), 
                                ('in_progress', 'In Progress'), 
                                ('completed', 'Completed')],
                        default='pending')
    submit = SubmitField('Save Task')