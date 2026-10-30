from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    shop_name = StringField("Shop name", validators=[DataRequired(), Length(max=200)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Register")

class ShopSettingsForm(FlaskForm):
    shop_name = StringField("Shop name", validators=[DataRequired(), Length(max=200)])
    submit = SubmitField("Save shop name")

class ProductForm(FlaskForm):
    sku = StringField("SKU", validators=[Optional(), Length(max=64)])
    name = StringField("Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])
    price = DecimalField("Price", validators=[DataRequired(), NumberRange(min=0)])
    cost = DecimalField("Cost", validators=[Optional(), NumberRange(min=0)])
    quantity_in_stock = IntegerField("Quantity", validators=[Optional()])
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[Optional()])
    submit = SubmitField("Save")