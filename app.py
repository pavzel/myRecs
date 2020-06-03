import os
from flask import Flask, render_template, redirect, request, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import env as config

app = Flask(__name__)

app.config["MONGO_DBNAME"] = 'myRecsDB'
app.config["MONGO_URI"] = os.environ.get('MONGO_URI')

mongodb = PyMongo(app)

def find_best():
    return mongodb.db.myRecPlaces.find({"my_opinion": 3})

@app.route('/')
def get_places():
    places = mongodb.db.myRecPlaces.find()
    best = find_best()
    return render_template('places.html', places = places, best = best)

@app.route('/place_details/<place_id>')
def place_details(place_id):
    place = mongodb.db.myRecPlaces.find_one({"_id": ObjectId(place_id)})
    return render_template('placedetails.html', place = place)

@app.route('/edit_place_details/<place_id>')
def edit_place_details(place_id):
    place = mongodb.db.myRecPlaces.find_one({"_id": ObjectId(place_id)})
    return render_template('editplacedetails.html', place = place)

if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=os.environ.get('PORT'),
            debug=True)