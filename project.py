from functools import wraps
from flask import Flask
from flask import render_template
from flask import request, redirect
from flask import jsonify
from flask import url_for
from flask import flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Catalog, MenuItem, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Catalog Menu Application"


# Connect to Database and create database session
engine = create_engine('sqlite:///catalogwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in login_session:
            return redirect(url_for('showLogin'))
        return f(*args, **kwargs)
    return decorated_function


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


# CONNECT to Facebook
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (  # noqa
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.8/me"
    # strip expire tag from access token
    token = result.split("&")[0]

    url = 'https://graph.facebook.com/v2.8/me?fields=id%2Cname%2Cemail%2Cpicture&access_token=' + access_token  # noqa
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = token

    # Get user picture
    login_session['picture'] = data["picture"]["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '  # noqa

    flash("Now logged in as %s" % login_session['username'])
    return output


# Disconnect with Facebook
@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)  # noqa
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


# CONNECT to Google
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),  # noqa
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '  # noqa
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# User Helper Functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# -------------------------------------
# JSON APIs to view Catalog Information
# -------------------------------------
# Returns JSON of all items in catalog
@app.route('/catalog.json')
def catalogMenuJSON():
    items = session.query(MenuItem).order_by(
        MenuItem.id.desc())
    return jsonify(MenuItems=[i.serialize for i in items])


# Returns JSON of selected item in catalog
@app.route('/catalog/<int:catalog_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(catalog_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


# Returns JSON of all menuitems in catalog
@app.route('/catalog/JSON')
def catalogsJSON():
    catalogs = session.query(Catalog).all()
    return jsonify(catalogs=[r.serialize for r in catalogs])


# ---------------------
# CRUD for CATALOG
# ---------------------
# Show all catalogs
@app.route('/')
@app.route('/catalog/')
def showCatalogs():
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    if 'username' not in login_session:
        return render_template(
            'publiccatalogs.html',
            catalogs=catalogs
            )
    else:
        return render_template('catalogs.html', catalogs=catalogs)


# Create a new catalog
@app.route('/catalog/new/', methods=['GET', 'POST'])
@login_required
def newCatalog():
    if request.method == 'POST':
        if request.form['name']:
            newCatalog = Catalog(
                name=request.form['name'], user_id=login_session['user_id'])
            session.add(newCatalog)
            flash(
                'New Catalog %s Successfully Created'
                % newCatalog.name
                )
            session.commit()
            return redirect(url_for('showCatalogs'))
        else:
            flash('Please Complete Name Field')
            return render_template('newCatalog.html')
    else:
        return render_template('newCatalog.html')


# Edit a Catalog
@app.route('/Catalog/<int:catalog_id>/edit/', methods=['GET', 'POST'])
@login_required
def editCatalog(catalog_id):
    editedCatalog = session.query(
        Catalog).filter_by(id=catalog_id).one()
    if editedCatalog.user_id != login_session['user_id']:
        return """<script>function myFunction()
                    {alert('You are not authorized to edit
                    this catalog. Please create your own
                    catalog in order to edit.');}</script>
                    <body onload='myFunction()''>"""
    if request.method == 'POST':
        if request.form['name']:
            editedCatalog.name = request.form['name']
            flash('Catalog Successfully Edited %s' % editedCatalog.name)
            return redirect(url_for('showMenu', catalog_id=catalog_id))
        else:
            return redirect(url_for(
                'editCatalog',
                catalog_id=catalog_id)
                )
    else:
        return render_template(
            'editCatalog.html',
            catalog=editedCatalog
            )


# Delete a catalog
@app.route('/catalog/<int:catalog_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteCatalog(catalog_id):
    catalogToDelete = session.query(
        Catalog).filter_by(id=catalog_id).one()
    if catalogToDelete.user_id != login_session['user_id']:
        return """<script>function myFunction()
                {alert('You are not authorized to delete
                this catalog. Please create your own
                catalog in order to delete.');}</script>
                <body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(catalogToDelete)
        flash('%s Successfully Deleted' % catalogToDelete.name)
        session.commit()
        return redirect(url_for(
                'showCatalogs',
                catalog_id=catalog_id)
                )
    else:
        return render_template(
            'deleteCatalog.html',
            catalog=catalogToDelete
            )


# ---------------------
# CRUD for ITEMS
# ---------------------
# Show a catalog menu items
@app.route('/catalog/<int:catalog_id>/')
@app.route('/catalog/<int:catalog_id>/menu/')
def showMenu(catalog_id):
    catalog = session.query(Catalog).filter_by(id=catalog_id).one()
    creator = getUserInfo(catalog.user_id)
    items = session.query(MenuItem).filter_by(
        catalog_id=catalog_id).all()
    if ('username' not in login_session or
            creator.id != login_session['user_id']):
        return render_template(
            'publicmenu.html',
            items=items,
            catalog=catalog,
            creator=creator
            )
    else:
        return render_template(
            'menu.html',
            items=items,
            catalog=catalog,
            creator=creator
            )


# Create a new menu item
@app.route(
    '/catalog/<int:catalog_id>/menu/new/',
    methods=['GET', 'POST']
)
@login_required
def newMenuItem(catalog_id):
    catalog = session.query(Catalog).filter_by(id=catalog_id).one()
    if login_session['user_id'] != catalog.user_id:
        return """<script>function myFunction()
                {alert('You are not authorized to add
                menu items to this catalog. Please create
                your own catalog in order to add items.');
                }</script><body onload='myFunction()''>"""
    if request.method == 'POST':
        if (request.form['name'] and request.form['description'] and
                request.form['price'] and request.form['category']):
            newItem = MenuItem(
                        name=request.form['name'],
                        description=request.form['description'],
                        price=request.form['price'],
                        category=request.form['category'],
                        catalog_id=catalog_id,
                        user_id=catalog.user_id
                    )
            session.add(newItem)
            session.commit()
            flash('New Menu %s Item Successfully Created' % (newItem.name))
            return redirect(url_for('showMenu', catalog_id=catalog_id))
        else:
            flash("Please Fill Out All The Form Before Submitting")
            return redirect(url_for('newMenuItem',
                                    catalog_id=catalog_id,
                                    catalog=catalog))
    else:
        return render_template(
                    'newmenuitem.html',
                    catalog_id=catalog_id,
                    catalog=catalog
        )


# Edit a menu item
@app.route(
    '/catalog/<int:catalog_id>/menu/<int:menu_id>/edit',
    methods=['GET', 'POST']
)
@login_required
def editMenuItem(catalog_id, menu_id):
    editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
    catalog = session.query(Catalog).filter_by(id=catalog_id).one()
    if login_session['user_id'] != catalog.user_id:
        return """<script>function myFunction()
                {alert('You are not authorized to edit
                menu items to this catalog. Please create
                your own catalog in order to edit items.');
                }</script><body onload='myFunction()''>"""
    if request.method == 'POST':
        if (request.form['name'] and request.form['description'] and
                request.form['price']and request.form['category']):
            editedItem.name = request.form['name']
            editedItem.category = request.form['category']
            editedItem.description = request.form['description']
            editedItem.price = request.form['price']
            editedItem.catalog_id = catalog.id
            session.add(editedItem)
            session.commit()
            flash('Menu Item Successfully Edited')
            return redirect(url_for('showMenu',
                                    catalog_id=catalog_id))
        else:
            flash("Do Not Leave Any Blanks")
            return redirect(url_for('editMenuItem',
                                    catalog_id=catalog_id,
                                    menu_id=menu_id,
                                    item=editedItem,
                                    catalog=catalog))
    else:
        return render_template(
            'editmenuitem.html',
            catalog_id=catalog_id,
            menu_id=menu_id,
            item=editedItem,
            catalog=catalog
        )


# Delete a menu item
@app.route(
    '/catalog/<int:catalog_id>/menu/<int:menu_id>/delete',
    methods=['GET', 'POST']
)
@login_required
def deleteMenuItem(catalog_id, menu_id):
    catalog = session.query(Catalog).filter_by(id=catalog_id).one()
    itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
    if login_session['user_id'] != catalog.user_id:
        return """<script>function myFunction()
                {alert('You are not authorized to delete
                menu items to this catalog. Please create
                your own catalog in order to delete items.')
                ;}</script><body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', catalog_id=catalog_id))
    else:
        return render_template(
            'deleteMenuItem.html',
            item=itemToDelete,
            catalog=catalog
        )


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showCatalogs'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCatalogs'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
