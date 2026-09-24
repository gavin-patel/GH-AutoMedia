from PIL import Image, ImageOps
import os
import cv2
import json
import numpy as np


def calculate_sharpness(image):
    gray = np.asarray(image.convert("L"))
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def process_photo(input_path):
    final_width = 1080
    final_height = 1920
    border = 20
    image_width = final_width - (border * 2)
    image_height = final_height - (border * 2)

    output_folder = "processed"
    os.makedirs(output_folder, exist_ok=True)

    filename = os.path.basename(input_path)
    name = os.path.splitext(filename)[0]
    output_path = os.path.join(output_folder, name + "_story.jpg")

    print("Processing:", filename)

    image = Image.open(input_path)
    if image.format == "JPEG":
        image.draft("RGB", (2048, 2048))
    image.load()
    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)

    sharpness = calculate_sharpness(image)
    print("Sharpness score:", round(sharpness, 2))

    status = "Sharp" if sharpness >= 100 else "Possibly Blurry"

    image = ImageOps.fit(
        image,
        (image_width, image_height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5)
    )
    image = ImageOps.expand(image, border=border, fill="white")
    image.save(output_path, quality=95)

    analysis = {
        "filename": filename,
        "sharpness": round(sharpness, 2),
        "status": status
    }
    analysis_path = os.path.join(output_folder, name + "_analysis.json")
    with open(analysis_path, "w") as file:
        json.dump(analysis, file, indent=4)

    print("Created:", output_path)
    print("Analysis saved:", analysis_path)