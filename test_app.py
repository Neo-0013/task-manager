# test_app.py - Simple Flask Test
# Put this in your project root (same level as run.py)

from flask import Flask, render_template

app = Flask(__name__, template_folder='app/templates')

@app.route('/')
def test():
    return render_template('test.html', name="Flask")

if __name__ == '__main__':
    app.run(debug=True, port=5001)
