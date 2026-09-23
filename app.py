from flask import Flask, render_template, send_from_directory, redirect, url_for, request
import os
import shutil
import json

from processor import process_photo

app = Flask(__name__)

PROCESSED_FOLDER = "processed"
APPROVED_FOLDER = "approved"
REJECTED_FOLDER = "rejected"
UPLOAD_FOLDER = "cloud_input"

os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(APPROVED_FOLDER, exist_ok=True)
os.makedirs(REJECTED_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    photos = []

    for filename in os.listdir(PROCESSED_FOLDER):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):

            name = os.path.splitext(filename)[0]

            analysis_filename = name.replace("_story", "") + "_analysis.json"

            analysis_path = os.path.join(
                PROCESSED_FOLDER,
                analysis_filename
            )

            analysis = {
                "sharpness": "Unknown",
                "status": "Unknown"
            }

            if os.path.exists(analysis_path):
                with open(analysis_path, "r") as file:
                    analysis = json.load(file)

            photos.append({
                "filename": filename,
                "sharpness": analysis["sharpness"],
                "status": analysis["status"]
            })

    photos.sort(
        key=lambda photo: photo["sharpness"]
        if isinstance(photo["sharpness"], (int, float))
        else 0,
        reverse=True
    )

    return render_template("index.html", photos=photos)


@app.route("/upload", methods=["POST"])
def upload():
    if "photo" not in request.files:
        return "No photo uploaded", 400

    file = request.files["photo"]

    if file.filename == "":
        return "No photo selected", 400

    filename = os.path.basename(file.filename)

    input_path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(input_path)

    process_photo(input_path)

    return redirect(url_for("home"))


@app.route("/photo/<filename>")
def photo(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)


@app.route("/approve/<filename>")
def approve(filename):
    source = os.path.join(PROCESSED_FOLDER, filename)
    destination = os.path.join(APPROVED_FOLDER, filename)

    shutil.move(source, destination)

    return redirect(url_for("home"))


@app.route("/reject/<filename>")
def reject(filename):
    source = os.path.join(PROCESSED_FOLDER, filename)
    destination = os.path.join(REJECTED_FOLDER, filename)

    shutil.move(source, destination)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )