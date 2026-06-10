import os
import json
import datetime
import threading
from flask import Flask, render_template, request, jsonify
from ps_worker import PowerShellWorker

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True

CONFIG_DIR = "configs"
SCRIPT_DIR = "scripts"
LOG_FILE = "logs/app.log"

_ps = None
_ps_lock = threading.Lock()

def get_ps():
    global _ps
    with _ps_lock:
        if _ps is None:
            log("Initializing PowerShell Worker...")
            _ps = PowerShellWorker()
    return _ps


def log(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {message}\n")


def load_configs():
    configs = []
    for file in os.listdir(CONFIG_DIR):
        if file.endswith(".json"):
            with open(os.path.join(CONFIG_DIR, file), encoding="utf-8") as f:
                configs.append(json.load(f))
    return configs


#  robuuste waarde extractor
def get_values(values, name):
    if hasattr(values, "getlist"):
        vals = values.getlist(name)
        return [v for v in vals if v not in (None, "", "false")]
    else:
        v = values.get(name)
        if isinstance(v, list):
            return v
        return [v] if v else []


def build_ps_args(params, values):
    args = []

    for p in params:
        name = p["name"]
        p_type = p.get("type")

        raw_values = get_values(values, name)

        #  SWITCH (checkbox)
        if p_type == "checkbox":
            if raw_values:
                args.append(f"-{name}")

        #  ARRAY (checkbox-list)
        elif p_type == "checkbox-list":
            if raw_values:
                safe = [str(v).replace("'", "''") for v in raw_values]
                ps_array = "@(" + ",".join(f"'{v}'" for v in safe) + ")"
                args.append(f"-{name} {ps_array}")

        #  NUMBER (FIX VOOR JOUW BUG)
        elif p_type == "number":
            if raw_values:
                try:
                    num = int(raw_values[0])
                    args.append(f"-{name} {num}")
                except ValueError:
                    raise ValueError(f"{name} must be a number")
                
        elif p_type == "textarea-array":
            if raw_values:
                # textarea komt als 1 string → splits op newline
                lines = raw_values[0].splitlines()

                values_clean = [v.strip() for v in lines if v.strip()]

                if values_clean:
                    safe = [str(v).replace("'", "''") for v in values_clean]
                    ps_array = "@(" + ",".join(f"'{v}'" for v in safe) + ")"
                    args.append(f"-{name} {ps_array}")


        #  TEXT / SELECT
        else:
            if raw_values:
                safe = str(raw_values[0]).replace("'", "''")
                args.append(f"-{name} '{safe}'")

    return " ".join(args)


def get_all_parameters(config):
    if "parameterSets" in config:
        return [
            p
            for s in config["parameterSets"]
            for p in s.get("parameters", [])
        ]
    return config.get("parameters", [])


def run_script(config, form_values):
    try:
        script_path = os.path.join(SCRIPT_DIR, config["script"])

        params = get_all_parameters(config)

        #  HIER invoegen
        for p in params:
            if p.get("required"):
                values = get_values(form_values, p["name"])
                if not values:
                    raise ValueError(f"{p['label']} is required")

        # daarna pas args bouwen
        args = build_ps_args(params, form_values)

        log(f"RUN {config['name']}")

        output = get_ps().run(script_path, args)

        log("OUTPUT: [suppressed]")

        exit_code = 0
        if any(x in output.lower() for x in ["error", "exception", "failed"]):
            exit_code = 1

        return {
            "stdout": output,
            "stderr": "",
            "exit_code": exit_code
        }

    except Exception as e:
        log(f"EXCEPTION: {str(e)}")

        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1
        }


@app.route("/")
def index():
    return render_template("index.html", configs=load_configs())


@app.route("/graph/status")
def graph_status():
    return jsonify({"status": get_ps().get_status()})


@app.route("/graph/connect", methods=["POST"])
def graph_connect():
    output = get_ps().connect()
    return jsonify({"output": output, "status": get_ps().get_status()})


@app.route("/graph/disconnect", methods=["POST"])
def graph_disconnect():
    output = get_ps().disconnect()
    return jsonify({"output": output, "status": get_ps().get_status()})


@app.route("/form/<id>")
def form(id):
    config = next((c for c in load_configs() if c["id"] == id), None)
    return render_template("form.html", config=config)


@app.route("/run/<id>", methods=["POST"])
def run(id):
    try:
        config = next((c for c in load_configs() if c["id"] == id), None)

        if not config:
            return jsonify({"stderr": "Config not found", "exit_code": 1}), 404

        return jsonify(run_script(config, request.form))

    except Exception as e:
        log(f"ERROR: {str(e)}")

        return jsonify({
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1
        }), 500


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    print("Use waitress to run this app in production.")
    app.run(host="127.0.0.1", debug=True, port=5000)