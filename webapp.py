import os
from flask import Flask, redirect
from subprocess import PIPE, Popen

app = Flask(__name__)

@app.route("/")
def index():
    return redirect("/static/index.html", code=302)
 
@app.route("/api/reboot", methods=['POST'])
def reboot():
    p = Popen("sudo reboot", shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    return stdout + stderr

@app.route("/api/poweroff", methods=['POST'])
def poweroff():
    p = Popen("sudo poweroff", shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    return stdout + stderr

@app.route("/maple.log")
def log():
    with open('/home/mark/maple.log', 'r') as f:
     return f.read()

 
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
    