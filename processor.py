from PIL import Image, ImageOps
import os
import cv2
import json
import numpy as np


def calculate_sharpness(image):
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _save_processed_image(image, filename, sharpness):
    final_width = 1080
    final_height = 1920
    border = 20
    image_width = final_width - (border * 2)
    image_height = final_height - (border * 2)

    output_folder = "processed"
    os.makedirs(output_folder, exist_ok=True)

    name = os.path.splitext(filename)[0]
    output_path = os.path.join(output_folder, name + "_story.jpg")

    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)

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


def process_photo(input_path):
    filename = os.path.basename(input_path)
    print("Processing:", filename)

    with Image.open(input_path) as source:
        max_dimension = max(source.size)

    if max_dimension > 8192:
        decode_flag = cv2.IMREAD_REDUCED_COLOR_8
    elif max_dimension > 4096:
        decode_flag = cv2.IMREAD_REDUCED_COLOR_4
    elif max_dimension > 2048:
        decode_flag = cv2.IMREAD_REDUCED_COLOR_2
    else:
        decode_flag = cv2.IMREAD_COLOR

    decoded_image = cv2.imread(input_path, decode_flag)
    if decoded_image is None:
        raise ValueError("Unable to decode the uploaded image")

    sharpness = calculate_sharpness(decoded_image)
    image = Image.fromarray(cv2.cvtColor(decoded_image, cv2.COLOR_BGR2RGB))
    _save_processed_image(image, filename, sharpness)


def process_raw_photo(input_path):
    import rawpy

    filename = os.path.basename(input_path)
    print("Processing CR3 preview:", filename)
    with rawpy.imread(input_path) as raw:
        decoded_image = raw.postprocess(
            use_camera_wb=True,
            half_size=True,
            output_bps=8,
            no_auto_bright=True,
        )

    image = Image.fromarray(decoded_image).convert("RGB")
    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    rgb_image = np.asarray(image)
    bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    sharpness = calculate_sharpness(bgr_image)
    _save_processed_image(image, filename, sharpness)