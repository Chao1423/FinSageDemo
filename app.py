from flask import Flask, g , url_for, render_template, request, redirect, session, flash, jsonify
import pandas as pd
import numpy as np
import json, flask_login, datetime, requests, base64
from hashlib import sha256
from tools import *
from io import BytesIO
import matplotlib.pyplot  as plt
plt.switch_backend('Agg')
plt.ion()
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from bs4 import BeautifulSoup
from collections import defaultdict


app = Flask(__name__)
app.secret_key = "9773e89f69e69285cf11c10cbc44a37945f6abbc5d78d5e20c2b1b0f12d75ab7"
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

global USER_CREDENTIALS,TOOL_PATH,manager
USER_CREDENTIALS = 'static/users/users.json'
TOOL_PATH = 'static/tools/tools.json'

@app.before_request
def load_user_file():
    if flask_login.current_user.is_authenticated:
        g.username = flask_login.current_user.username
        g.filename = f"static/users/{g.username}/{g.username}'s_assistants.json"
        try:
            with open(g.filename, 'r') as file:
                g.assistants = json.load(file)
        except FileNotFoundError:
            g.assistants = {}
    else:
        g.filename = g.username = None

@login_manager.user_loader
def load_user(userid):
    user_json = pd.read_json(USER_CREDENTIALS).get(userid)
    return User(user_json['username'],
                user_json['email'],
                user_json['password'])

@app.get('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['GET', 'POST'])
@flask_login.login_required
def chatbot():
    if request.method == 'POST':
        if 'create_new' in request.form:
            return redirect(url_for('chatbot'))
        if 'selected_assistant' in request.form:
            asst_id = request.form['selected_assistant']
            return redirect(url_for('chat_with_assistant', asst_id=asst_id))
        asst_name = request.form.get('asst_name')
        instruction = request.form.get('instruction')
        tools_list = request.form.getlist('tools[]') 
        model = request.form.get('model')

        with open(TOOL_PATH, 'r') as file:
            data = json.load(file)
        tools_lib = data['tools']
        
        matched_tools = []
        for tool_name in tools_list:
            for tool in tools_lib:
                if tool['function']['name'] == tool_name:
                    matched_tools.append(tool)
                    break  

        g.manager = AssistantManager(g.username)
        g.manager.create_assistant(asst_name,instruction,matched_tools,model)
        new_asst_id = g.manager.assistant_id
        return redirect(url_for('chat_with_assistant', asst_id=new_asst_id))

    return render_template('chat.html', assistants=g.assistants)

@app.route('/chat/<asst_id>', methods=['GET', 'POST'])
def chat_with_assistant(asst_id):
    g.manager = AssistantManager(g.username,asst_id)
    #if 'chat_history' not in session:
        #session['chat_history'] = [] 
    if request.method == 'POST':
        data = request.get_json()
        user_message = data.get('user_message', '')
        if user_message:
            response_message = process_message(user_message)
            session['chat_history'].append((f'{g.username}', user_message))
            session['chat_history'].append((g.assistants[asst_id]['name'], response_message))
            session.modified = True 
            g.manager.record.add_history(asst_id,session['chat_history'])
            #print(f"graph ------------> {g.manager.graph}")
            if g.manager.graph:
                plotly_json = json.loads(g.manager.graph)
                return jsonify({
                    'type': 'chat',
                    'response': response_message,
                    'plotlyData': {
                        'data': plotly_json['data'],
                        'layout': plotly_json['layout']
                    }
                })
            else:
                return jsonify({
                    'type': 'chat',
                    'response': response_message,
                    'plotlyData': None
                })
        return jsonify({'error': 'No message received'}), 400 
    else:
        session['chat_history'] = g.manager.record.retrieve_history(asst_id)
        return render_template('chat_with_assistant.html', assistants=g.assistants, asst_id=asst_id, chat_history=session['chat_history'])
def process_message(message):
    g.manager.add_message_to_thread("user",message)
    g.manager.run_assistant(None)
    response = g.manager.wait_for_completed()
    return response

@app.route('/chat/<asst_id>/delete', methods=['POST'])
@flask_login.login_required
def delete_assistant(asst_id):
    try:
        g.manager = AssistantManager(g.username,asst_id)
        print(g.manager.assistant_id)
        g.manager.delete()
        return jsonify({'success': True, 'type': 'delete'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'type': 'delete'})
    
@app.route('/stocks/<asst_id>', methods=['GET', 'POST'])
def stock_data(asst_id):
    manager = AssistantManager(g.username,asst_id)
    graphJSON = manager.graph
    return render_template('show_data.html', graphJSON=graphJSON)

@app.route('/news')
def news():
    return render_template('news.html')

@app.route('/machine_learning')
def machine_learning():
    return render_template('machine_learning.html')

@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')

@app.route("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    session.pop('chat_history', None)
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('password')
        user_existing = pd.read_json(USER_CREDENTIALS).T

        if username in user_existing['username'].to_list():
            return render_template('signup.html', msg='username')
        else:
            if confirm_password == password:
                password_hash = sha256(password.encode('utf-8')).hexdigest()
                user_series = pd.Series(dict(username=username, password=password_hash, email=email))
                user_existing.loc[sha256(username.encode('utf-8')).hexdigest()] = user_series
                user_existing.to_json(USER_CREDENTIALS, orient='index')
                return redirect(url_for('login', msg='signup'))
            else:
                return render_template('signup.html', msg='password')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'login' in request.form:
        username = request.form['username']
        password = request.form['password']
        userid = sha256(username.encode('utf-8')).hexdigest()
        password_hash = sha256(password.encode('utf-8')).hexdigest()

        user_json = pd.read_json(USER_CREDENTIALS).get(userid)
        if user_json is None:
            return render_template('login.html', msg="mismatch")
        user = User(user_json['username'], user_json['email'], user_json['password'])
        if password_hash != user.password:
            return render_template('login.html', msg="mismatch")
        else:
            flask_login.login_user(user)
            flash("You're logged in!")
            return redirect(url_for('index'))
    elif request.method == 'POST' and 'signup' in request.form:
        return redirect(url_for('signup'))
    return render_template('login.html', msg=request.args.get('msg'))

@app.route('/user_profile/<name>', methods=['GET'])
@flask_login.login_required
def user(name):
    return render_template('user_profile.html', edit='No',
                           name=flask_login.current_user.username)

@app.route('/user_profile/<name>', methods=['POST'])
@flask_login.login_required
def user_edit(name):
    user = flask_login.current_user
    if 'editEmail' in request.form:
        return render_template('user_profile.html', edit="Yes",name=user.username)
    elif 'deleteAccount' in request.form:
        hashed_username = sha256(user.username.encode('utf-8')).hexdigest()
        flask_login.logout_user()
        with open(USER_CREDENTIALS, 'r') as file:
            users = json.load(file)
        if hashed_username in users:
            del users[hashed_username]
        with open(USER_CREDENTIALS, 'w') as file:
            json.dump(users, file)
        return redirect(url_for('index')) 
    else:
        new_email = request.form['email']
        user_json = pd.read_json(USER_CREDENTIALS)
        user_json.loc['email', user.id] = new_email
        user_json.to_json(USER_CREDENTIALS)
        user = User(*user_json[user.id].values)
        return redirect(url_for('user', name=user.username))


if __name__ == '__main__':
    app.debug = False
    app.run(host='0.0.0.0', port=80)  
      
