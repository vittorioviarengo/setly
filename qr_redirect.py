from flask import Flask, redirect, url_for, session
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = b'3L+nc\xcd\x02e/\x88\xbf\x9e\xfc\xb5\xa2'
babel = Babel(app)

@app.route('/qr-redirect')
def qr_redirect():
    # Generate current timestamp
    current_timestamp = datetime.datetime.now().timestamp()

    # Redirect to the main app with the timestamp
    return redirect(url_for('main_app', timestamp=current_timestamp))

@app.route('/main')
def main_app():
    # Store the timestamp in session
    session['timestamp'] = request.args.get('timestamp')
    return render_template('main.html')
