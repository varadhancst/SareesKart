import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_bcrypt import Bcrypt
from datetime import datetime
import stripe
from flask_sqlalchemy_report import Reporter

from dotenv import load_dotenv

load_dotenv()

# stripe.api_key = os.getenv('stripe_test_api_key')
stripe.api_key = os.getenv('stripe_live_api_key')

login_manager = LoginManager()
app = Flask(__name__, template_folder='templates', static_folder='static')

YOUR_DOMAIN = 'http://localhost:5000'
login_manager.init_app(app)
bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///silks-store.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'user'

    email = db.Column(db.String, primary_key=True)
    password = db.Column(db.String)
    authenticated = db.Column(db.Boolean, default=False)

    def is_active(self):
        return True

    def get_id(self):
        return self.email

    def is_authenticated(self):
        return self.authenticated

    def is_anonymous(self):
        return False


class Items(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    image = db.Column(db.String(250), nullable=False)
    price = db.Column(db.Float, nullable=False)
    price_id = db.Column(db.String(250), nullable=False)

    def __repr__(self):
        return '<Items %r>' % self.name


db.create_all()

# user = User( email="example@gmail.com", password=bcrypt.generate_password_hash('Example'))
# db.session.add(user)
# db.session.commit()

year = datetime.now().year


@login_manager.user_loader
def user_loader(user_id):
    return User.query.get(user_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.get(request.form.get("email"))
        if user:
            if bcrypt.check_password_hash(user.password, request.form.get("password")):
                user.authenticated = True
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["GET"])
@login_required
def logout():
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    return redirect(url_for('index'))


@app.route('/')
def index():
    all_items = db.session.query(Items).all()
    total_items = len(all_items)
    return render_template('index.html', all_items=all_items, total_items=total_items)


@app.route('/add', methods=("POST", "GET"))
@login_required
def add():
    if request.method == "POST":
        name = request.form.get("name")
        url_image = request.form.get("urlimage")
        price = float(request.form.get("price"))
        product_id = stripe.Product.create(name=name, images=[url_image])
        price_id = stripe.Price.create(product=product_id.id, unit_amount=int(price * 100), currency="inr")
        new_item = Items(name=name, image=url_image, price=price, price_id=price_id.id)
        db.session.add(new_item)
        db.session.commit()
        return redirect('/')
    return render_template('add.html')


@app.route('/delete')
@login_required
def delete():
    all_items = db.session.query(Items).all()
    return render_template('delete.html', all_items=all_items)


@app.route('/delete/<int:id>', methods=['POST', 'GET'])
@login_required
def delete_item(id):
    item = Items.query.filter_by(id=id).first()
    if request.method == "POST":
        item_to_delete = Items.query.get(id)
        db.session.delete(item_to_delete)
        db.session.commit()
        return redirect('/delete')
    return render_template('deleteitem.html', item=item)


@app.route('/update')
@login_required
def update():
    all_items = db.session.query(Items).all()
    total_items = len(all_items)
    return render_template('update.html', all_items=all_items, total_items=total_items)


@app.route('/store')
def store():
    all_items = db.session.query(Items).all()
    return render_template('store.html', all_items=all_items)


@app.route('/salesReport', methods=['GET', 'POST'])
@login_required
def sales_report():
    reportTitle = "Stock details"
    sqlQuery = "SELECT id as 'ID', name as 'Name', image as 'Image url', price as 'Price' FROM Items"
    fontName = "Arial"
    headerRowBackgroundColor = '#ffeeee'
    evenRowsBackgroundColor = '#ffeeff'
    oddRowsBackgroundColor = '#ffffff'
    return Reporter.generateFromSql(db.session, reportTitle, sqlQuery, "ltr", fontName, "Price", True,
                                    headerRowBackgroundColor, evenRowsBackgroundColor,
                                    oddRowsBackgroundColor)


@app.route('/update/<int:id>', methods=["POST", "GET"])
@login_required
def update_item(id):
    if request.method == "POST":
        item_to_update = Items.query.get(id)
        item_to_update.name = request.form.get("name")
        item_to_update.image = request.form.get("urlimage")
        item_to_update.price = request.form.get("price")
        db.session.commit()
        return redirect('/update')
    item = Items.query.filter_by(id=id).first()
    return render_template('updateitem.html', item=item)


@app.route('/create-checkout-session/<string:price_id>', methods=['POST'])
def create_checkout_session(price_id):
    try:
        checkout_session = stripe.checkout.Session.create(line_items=[{'price': price_id, 'quantity': 1, }, ],
                                                          mode='payment', success_url=YOUR_DOMAIN + '/success',
                                                          cancel_url=YOUR_DOMAIN + '/cancel')
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


@app.route('/cancel')
def cancel():
    return render_template('cancel.html')


@app.route('/success')
def success():
    return render_template('success.html')


@app.route('/sarees')
def sarees():
    return render_template('sarees.html')


@app.route('/report')
def report():
    all_reports = db.session.query(Items).all()
    return render_template('report.html', all_reports=all_reports)


@app.route('/search', methods=['GET', 'POST'])
def search():
    search_item = request.args.get("search")
    print(search_item)
    search_item = "%{}%".format(search_item)
    products = db.session.query(Items.name.like(search_item)).all()
    return render_template("search.html", search=search_item, products=products)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    # app.run(debug=True)
