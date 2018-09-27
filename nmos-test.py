# Copyright (C) 2018 Riedel Communications GmbH & Co. KG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from flask import Flask, render_template, flash, request, jsonify
from wtforms import Form, validators, StringField, SelectField, IntegerField

import git
import os
import time

import IS0401Test
import IS0402Test
import IS0501Test
import IS0601Test

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = 'nmos-interop-testing-jtnm'

CACHE_PATH = 'cache'

class DataForm(Form):
    test = SelectField(label="Select test:", choices=[("IS-04-01", "IS-04-01: Node"), ("IS-04-02", "IS-04-02: Registry"), ("IS-05-01", "IS-05-01: ConnectionMgmt API"), ("IS-06-01", "IS-06-01: Network Control API")])
    #TODO: Potentially add a mixed IS-04/05 test for where they cross over
    ip = StringField(label="Ip:", validators=[validators.IPAddress(message="Please enter a valid IPv4 address.")])
    port = IntegerField(label="Port:", validators=[validators.NumberRange(min=0, max=65535,
                                                                          message="Please enter a valid port number (0-65535).")])
    version = SelectField(label="API Version:", choices=[("v1.0", "v1.0"),
                                                        ("v1.1", "v1.1"),
                                                        ("v1.2", "v1.2")])

class Registry(object):
    def __init__(self):
        self.last_time = 0
        self.last_hb_time = 0
        self.data = []
        self.heartbeats = []

    def reset(self):
        self.last_time = time.time()
        self.last_hb_time = 0
        self.data = []
        self.heartbeats = []

    def add(self, headers, payload):
        self.last_time = time.time()
        self.data.append((self.last_time, {"headers": headers, "payload": payload}))

    def heartbeat(self, headers, payload, node_id):
        self.last_hb_time = time.time()
        self.heartbeats.append((self.last_hb_time, {"headers": headers, "payload": payload, "node_id": node_id}))

    def get_data(self):
        return self.data

    def get_heartbeats(self):
        return self.heartbeats

REGISTRY = Registry()

# IS-04 resources
@app.route('/x-nmos/registration/v1.2/resource', methods=["POST"])
def reg_page():
    REGISTRY.add(request.headers, request.json)
    #TODO: Ensure status code returned is correct
    return jsonify(request.json["data"])

@app.route('/x-nmos/registration/v1.2/health/nodes/<node_id>', methods=["POST"])
def heartbeat(node_id):
    REGISTRY.heartbeat(request.headers, request.json, node_id)
    #TODO: Ensure status code returned is correct
    return jsonify({"health": int(time.time())})

# Index page
@app.route('/', methods=["GET", "POST"])
def index_page():
    form = DataForm(request.form)
    if request.method == "POST":
        test = request.form["test"]
        ip = request.form["ip"]
        port = request.form["port"]
        version = request.form["version"]
        base_url = "http://{}:{}".format(ip, str(port))
        if form.validate():
            if test == "IS-04-01":
                api_name = "node"
                spec_versions = ["v1.0", "v1.1", "v1.2"]
                spec_path = 'cache/is-04'

                url = "http://{}:{}/x-nmos/node/{}/".format(ip, str(port), version)
                test_obj = IS0401Test.IS0401Test(url, REGISTRY)
                result = test_obj.run_tests()
                return render_template("result.html", url=base_url, test=test, result=result)
            elif test == "IS-04-02":
                api_name = "node"
                spec_versions = ["v1.0", "v1.1", "v1.2"]
                spec_path = 'cache/is-04'

                test_obj = IS0402Test.IS0402Test(base_url, api_name, spec_versions, version, spec_path)
                result = test_obj.run_tests()
                return render_template("result.html", url=base_url, test=test, result=result)
            elif test == "IS-05-01":
                api_name = "connection"
                spec_versions = ["v1.0"]
                spec_path = 'cache/is-05'

                url = "http://{}:{}/x-nmos/connection/{}/".format(ip, str(port), version)
                test_obj = IS0501Test.IS0501Test(url)
                result = test_obj.run_tests()
                return render_template("result.html", url=base_url, test=test, result=result)
            elif test == "IS-06-01":
                api_name = "netctrl"
                spec_versions = ["v1.0"]
                spec_path = 'cache/is-06'

                test_obj = IS0601Test.IS0601Test(base_url, api_name, spec_versions, version, spec_path)
                result = test_obj.run_tests()
                return render_template("result.html", url=base_url, test=test, result=result)
        else:
            flash("Error: {}".format(form.errors))

    return render_template("index.html", form=form)


if __name__ == '__main__':
    print(" * Initialising specification repositories...")

    if not os.path.exists(CACHE_PATH):
        os.makedirs(CACHE_PATH)

    repositories = [('is-04', 'nmos-discovery-registration'),
                    ('is-05', 'nmos-device-connection-management'),
                    ('is-06', 'nmos-network-control')]
    for repo_data in repositories:
        path = os.path.join(CACHE_PATH + '/' + repo_data[0])
        if not os.path.exists(path):
            repo = git.Repo.clone_from('https://github.com/AMWA-TV/' + repo_data[1] + '.git', path)
        else:
            repo = git.Repo(path)
            repo.git.reset('--hard')
            #repo.remotes.origin.pull() # TODO: Uncomment for production use

    #TODO: Join 224.0.1.129 briefly and capture some announce messages

    print(" * Initialisation complete")

    app.run(host='0.0.0.0', threaded=True)
