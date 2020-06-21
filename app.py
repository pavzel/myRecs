import os
import math
import random
from flask import Flask, render_template, redirect, request, url_for, session
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = 'myRecsDB'
app.config["MONGO_URI"] = os.environ.get('MONGO_URI')
app.secret_key = os.environ.get("SECRET")

mongodb = PyMongo(app)


def get_photos_of_best_places(value):
    # Read data about 20 places with highest opinion values
    best_places = mongodb.db.myRecPlaces.find({"opinion": { "$gte": value } }).sort("opinion", -1).limit(20)
    # For each place get URL for a random photo
    best_place_images = []
    for place in best_places:
        place_photo = get_random_photo(place['users'])
        if place_photo:
            best_place_images.append(place_photo)
    # Return 3 random photos
    random.shuffle(best_place_images)
    return best_place_images[0:3]


def get_random_photo(users):
    users_photos = []
    for user in users:
        photo_url = users[user]['photo_url']
        if photo_url != '':
            users_photos.append(users[user]['photo_url'])
    random.shuffle(users_photos)
    if len(users_photos) == 0:
        output_url = None
    else:
        output_url = users_photos[0]
    return output_url


def update_countries(country):
    is_in_db = mongodb.db.countries.count_documents({"country_name": country})
    if is_in_db == 0:
        countries = mongodb.db.countries
        countries.insert_one({ 'country_name': country })


def calculate_users_opinion(users):
    users_opinion = 0
    users_opinions = []
    for user in users:
        users_opinion += int(users[user]['my_opinion'])
        users_opinions.append(int(users[user]['my_opinion']))
    users_opinion /= len(users_opinions)
    return users_opinion


def float_to_str_int(opinion):
    if opinion > 0:
        opinion_str = '+' + str(round(opinion, 2))
    else:
        opinion_str = str(round(opinion, 2))
    opinion_int = int(round(opinion))
    return opinion_str, opinion_int


def get_users_opinion(users):
    users_opinion = calculate_users_opinion(users)
    return float_to_str_int(users_opinion)


def read_from_buffer():
    place_opinion = {}
    buffer = mongodb.db.buffer.find()
    for item in buffer:
        place_opinion[item["id"]] = item["opinion"]
    return place_opinion


def write_to_buffer(places):
    buff_dict = []
    for place in places:
        buff_dict.append({"id": place['_id'], "opinion": place['opinion']})
    mongodb.db.buffer.delete_many({})
    mongodb.db.buffer.insert_many(buff_dict)


@app.route('/')
def get_all_places():
    # Read "_id" and "opinion" for all places, save them in "buffer" collection
    places = mongodb.db.myRecPlaces.find({}, {'opinion': 1})
    write_to_buffer(places)
    # Set display parameters
    session['nav_main'] = ["active", "", "", "", "", ""]
    session['title'] = "All places:"
    session['curr_page'] = 1
    session['is_rec'] = False
    return redirect(url_for('display_many_places', page_number=session['curr_page']))


@app.route('/places/<page_number>')
def display_many_places(page_number):
    PER_PAGE = 15
    # Read from "buffer" collections pairs id/opinion and save in dictionary
    place_opinion = read_from_buffer()
    # Sort places according to opinion
    list_for_sorting = []
    for place in place_opinion:
        list_for_sorting.append((place, place_opinion[place]))
    list_sorted = sorted(list_for_sorting, key=lambda tuple: tuple[1], reverse=True)
    # Calculate the range of documents to display
    total_number_of_places = len(place_opinion)
    max_page = math.ceil(total_number_of_places / PER_PAGE)
    session["curr_page"] = int(page_number)
    index_min = PER_PAGE * (session["curr_page"] - 1)
    index_max = PER_PAGE * session["curr_page"]
    if index_max > total_number_of_places:
        index_max = index_min + total_number_of_places % PER_PAGE
    # Out of the sorted list choose only those places that must be displayed on the current page
    place_list = []
    for index in range(index_min, index_max):
        place_list.append(list_sorted[index][0])
    # Get data places that must be displayed and save them in a dictionary 
    places = mongodb.db.myRecPlaces.find({"_id": { "$in": place_list } })
    places_dict = {}
    for place in places:
        places_dict[place['_id']] = place
    # For the selected places, prepare a list with data essential for display
    display_list = []
    for place_id in place_list:
        place = places_dict[place_id]
        place_name = place['place_name']
        photo_url = get_random_photo(place['users'])
        if photo_url is None:
            photo_url = 'https://via.placeholder.com/700x400/0000FF/FFFFFF/?text=No+photo+yet'
        if session['is_rec']:
            footer_text = "REC-opinion:"
        else:
            footer_text = "Users' opinion:"
        opinion_str, opinion_int = float_to_str_int(place_opinion[place_id])
        display_list.append({
            '_id': place['_id'],
            'photo_url': photo_url,
            'place_name': place_name,
            'footer_text': footer_text,
            'opinion_str': opinion_str,
            'opinion_int': opinion_int
        })
    # Set display parameters
    session['nav_curr'] = session['nav_main']
    return render_template('places.html',
                            places=display_list,
                            max_page=max_page,
                            head_imgs=get_photos_of_best_places(1),
                            session=session)


@app.route('/place/<place_id>')
def display_place(place_id):
    editor = session['logged_in_user'] if 'logged_in_user' in session else None
    # Get data about a place
    place = mongodb.db.myRecPlaces.find_one({"_id": ObjectId(place_id)})
    # Save data in a dictionary
    place_dict = {}
    for key in place:
        place_dict[key] = place[key]
    # Compose a dictionary with data for display
    place_dict2 = {}
    place_dict2['_id'] = place_dict['_id']
    if editor:
        place_dict2['status'] = 'contributor' if editor in place['users'] else 'visitor'
    else:
        place_dict2['status'] = 'anonymous'
    place_dict2['place_name'] = place_dict['place_name']
    place_dict2['country'] = place_dict['country']
    if place_dict2['status'] == 'contributor':
        place_dict2['my_opinion'] = int(place_dict['users'][editor]['my_opinion'])
        place_dict2['is_visited'] = place_dict['users'][editor]['is_visited']
    # Collect photos, websites and comment added by all users
    place_dict2['photo_urls'] = []
    place_dict2['websites'] = []
    place_dict2['comments'] = []
    users = place_dict['users']
    for user in users:
        if users[user]['photo_url'] != '':
            place_dict2['photo_urls'].append(users[user]['photo_url'])
        if users[user]['website'] != '':
            place_dict2['websites'].append(users[user]['website'])
        if users[user]['comment'] != '':
            place_dict2['comments'].append(users[user]['comment'])
    # If there is no photo yet, add a placeholder
    if len(place_dict2['photo_urls']) == 0:
        place_dict2['photo_urls'] = ['https://via.placeholder.com/700x400/0000FF/FFFFFF/?text=No+photo+yet']
    # Add users' opinion
    place_dict2['opinion_str'], place_dict2['opinion_int'] = get_users_opinion(users)
    # If the place is RECommended then add REC-opinion to "place" dictionary
    if session['is_rec']:
        place_opinion = read_from_buffer()
        rec_opinion = place_opinion[ObjectId(place_id)]
        place_dict2['rec_str'], place_dict2['rec_int'] = float_to_str_int(rec_opinion)
    # Set display parameters
    session['nav_curr'] = ["", "", "", "", "", ""]
    return render_template('place.html', place=place_dict2, session=session)


@app.route('/edit_place/<place_id>')
def edit_place(place_id):
    if 'logged_in_user' in session:
        editor = session['logged_in_user']
    else:
        return redirect(url_for('login', login_problem=False))
    place = mongodb.db.myRecPlaces.find_one({"_id": ObjectId(place_id)})
    # If no data were added by the user before then add basic data now
    if not (editor in place['users']):
        new_user = {}
        new_user['my_opinion'] = int(0)
        new_user['is_visited'] = bool(False)
        new_user['photo_url'] = ''
        new_user['website'] = ''
        new_user['comment'] = ''
        users = place['users']
        users[editor] = new_user
        places = mongodb.db.myRecPlaces
        places.update_one({"_id": ObjectId(place_id)}, {"$set": {'users': users}})
    # Set display parameters
    session['nav_curr'] = ["", "", "", "", "", ""]
    return render_template('editplace.html', place=place, editor=editor, session=session)


@app.route('/update_place/<place_id>', methods=["POST"])
def update_place(place_id):
    if 'logged_in_user' in session:
        editor = session['logged_in_user']
    else:
        return redirect(url_for('login', login_problem=False))
    places = mongodb.db.myRecPlaces
    # Update user-specific data
    place = places.find_one({"_id": ObjectId(place_id)})
    users = place['users']
    users[editor] = {'my_opinion': int(request.form.get('my_opinion')),
                     'is_visited': bool(request.form.get('is_visited')),
                     'photo_url': request.form.get('photo_url'),
                     'website': request.form.get('website'),
                     'comment': request.form.get('comment')
                    }
    places.update_one({"_id": ObjectId(place_id)}, {"$set": {'users': users}})
    # Update general data
    country = request.form.get('country')
    update_countries(country)
    opinion = calculate_users_opinion(users)
    places.update_one({"_id": ObjectId(place_id)}, {"$set": {
        'place_name': request.form.get('place_name'),
        'country': country,
        'opinion': opinion
    }})
    # Update buffer data, if necessary
    if not session['title'] == "RECommended places:":
        mongodb.db.buffer.update_one({"id": ObjectId(place_id)}, {"$set": {'opinion': opinion}})
    return redirect(url_for('display_many_places', page_number=session['curr_page']))


@app.route('/add_place')
def add_place():
    # Set display parameters
    session['nav_curr'] = ["", "active", "", "", "", ""]
    return render_template('addplace.html', session=session)


@app.route('/insert_place', methods=["POST"])
def insert_place():
    if 'logged_in_user' in session:
        editor = session['logged_in_user']
    else:
        return redirect(url_for('login', login_problem=False))
    # Get data from form and prepare for saving
    country = request.form.get('country')
    opinion = float(request.form.get('my_opinion'))
    my_opinion = int(opinion)
    is_visited = bool(request.form.get('is_visited'))
    # Update "countries" collection if necessary
    update_countries(country)
    # Add a record to "myRecPlaces" collection
    places = mongodb.db.myRecPlaces
    places.insert_one({
        'place_name': request.form.get('place_name'),
        'country': country,
        'added_by': editor,
        'opinion': opinion,
        'users': {
            editor: {
                'my_opinion': my_opinion,
                'is_visited': is_visited,
                'website': request.form.get('website'),
                'photo_url': request.form.get('photo_url'),
                'comment': request.form.get('comment')
            }
        }
    })
    return redirect(url_for('get_all_places'))


@app.route('/delete_place/<place_id>')
def delete_place(place_id):
    if 'logged_in_user' in session:
        editor = session['logged_in_user']
    else:
        return redirect(url_for('login', login_problem=False))
    places = mongodb.db.myRecPlaces
    #Delete user's record about the place
    place = places.find_one({"_id": ObjectId(place_id)})
    if editor == place['added_by']:
        # Delete the record form collection completely
        places.remove({'_id': ObjectId(place_id)})
    else:
        # Delete only those data about the place that were added by logged in user
        users = place['users']
        users.pop(editor)
        places.update_one({"_id": ObjectId(place_id)}, {"$set": {'users': users}})
        #Update users' opinion for the place
        place = places.find_one({"_id": ObjectId(place_id)})
        opinion = calculate_users_opinion(place['users'])
        places.update_one({"_id": ObjectId(place_id)}, {"$set": {'opinion': opinion}})
    return redirect(url_for('get_all_places'))


@app.route('/select')
def select():
    # Get country data 
    countries = mongodb.db.countries.find().sort("country_name")
    # Set display parameters
    session['nav_curr'] = ["", "", "active", "", "", ""]
    return render_template("select.html", countries=countries, session=session)


@app.route('/get_selested_places', methods=["POST"])
def get_selected_places():
    # Read "_id" and "opinion" for all places, save them in "buffer" collection
    selected_countries = request.form.getlist('country')
    places = mongodb.db.myRecPlaces.find({"country": {"$in": selected_countries}}, {'opinion': 1})
    write_to_buffer(places)
    # Set display parameters
    session['nav_main'] = ["", "", "active", "", "", ""]
    session['title'] = "Selected places:"
    session['curr_page'] = 1
    session['is_rec'] = False
    return redirect(url_for('display_many_places', page_number=session['curr_page']))


@app.route('/recommend')
def recommend():
    # Get data added by individual users about all places
    # and save them to a dictionary "place_dict"
    place_dict = {}
    places = mongodb.db.myRecPlaces.find({}, {'users': 1})
    for place in places:
        place_dict[place['_id']] = place['users']
    # Get all usernames and prepare a dictionary "user_dict"
    # for saving opinions of individual users
    user_dict = {}
    users = mongodb.db.users.find({}, {'username': 1})
    for user in users:
        user_dict[user['username']] = {}
    # For each user save 'is_visited' and 'my_opinion' in "user_dict"
    for place in place_dict:
        users_in_place = place_dict[place]
        for user in user_dict:
            if user in users_in_place:
                user_in_place = users_in_place[user]
                user_dict[user][place] = {
                    'is_visited': user_in_place['is_visited'],
                    'opinion': user_in_place['my_opinion']
                }
    # Separate data of the logged in user from the other users' data
    my_opinions = user_dict[session['logged_in_user']]
    user_dict.pop(session['logged_in_user'])
    # Calculate similarities
    similarity = {}
    for user in user_dict:
        user_opinions = user_dict[user]
        opinions_to_compare = []
        for place in my_opinions:
            if my_opinions[place]['is_visited']:
                my_opinion = my_opinions[place]['opinion']
                if place in user_opinions:
                    if user_opinions[place]['is_visited']:
                        user_opinion = user_opinions[place]['opinion']
                        opinions_to_compare.append({'my': my_opinion, 'other': user_opinion})
        if len(opinions_to_compare) > 0:
            sum_d2 = 0
            for opinion_pair in opinions_to_compare:
                sum_d2 += pow(opinion_pair['my'] - opinion_pair['other'], 2)
            similarity[user] = 1 - pow(sum_d2 / len(opinions_to_compare), 0.5) / 6
    # Find recommended places and calculate "REC"-opinion
    recs = []
    for place in place_dict:
        if (place in my_opinions) and my_opinions[place]['is_visited']:
            continue
        else:
            sum_opinions = 0
            sum_similarities = 0
            for user in similarity:
                user_opinions = user_dict[user]
                if place in user_opinions:
                    if user_opinions[place]['is_visited']:
                        sum_opinions += user_opinions[place]['opinion'] * similarity[user]
                        sum_similarities += similarity[user]
            if sum_similarities > 0:
                recs.append({"id": place, "opinion": round(sum_opinions / sum_similarities, 2)})
    if len(recs) > 0:
        # Save "_id" and "opinion" for RECommended places in "buffer" collection
        mongodb.db.buffer.delete_many({})
        mongodb.db.buffer.insert_many(recs)
        # Set display parameters
        session['nav_main'] = ["", "", "", "active", "", ""]
        session['title'] = "RECommended places:"
        session['curr_page'] = 1
        session['is_rec'] = True
        return redirect(url_for('display_many_places', page_number=session['curr_page']))
    else:
        return redirect(url_for('get_all_places'))


@app.route('/login/<login_problem>')
def login(login_problem):
    # Set display parameters
    session['nav_curr'] = ["", "", "", "", "active", ""]
    return render_template("login.html", login_problem=login_problem, session=session)


@app.route('/sign_in', methods=["POST"])
def sign_in():
    # Get login data from form
    username = request.form.get('username')
    password = request.form.get('password')
    # Check username and password and sign in
    users = mongodb.db.users
    if users.count_documents({'username': username}) == 1:
        user = users.find_one({'username': username})
        if user['password'] == password:
            session['logged_in_user'] = username
            return redirect(url_for('get_all_places'))
    # Inform about problems with sign in and try again
    return render_template("login.html", login_problem = True, session=session)


@app.route('/logout')
def logout():
    session.pop('logged_in_user', None)
    return redirect(url_for('get_all_places'))


@app.route('/sign_up/<signup_problem>')
def sign_up(signup_problem):
    # Set display parameters
    session['nav_curr'] = ["", "", "", "", "active", ""]
    return render_template('signup.html', signup_problem=signup_problem, session=session)


@app.route('/insert_user', methods=["POST"])
def insert_user():
    # Get user's data from form
    username = request.form.get('username')
    password = request.form.get('password')
    # Add user's data to "users" collection
    users = mongodb.db.users
    if users.count_documents({'username': username}) == 0:
        users.insert_one({'username': username, 'password': password})
        return redirect(url_for('login', login_problem = False))
    return render_template('signup.html', signup_problem = True, session=session)


@app.route('/help')
def help():
    # Set display parameters
    session['nav_curr'] = ["", "", "", "", "", "active"]
    return render_template('help.html')


if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=os.environ.get('PORT'),
            debug=False)
