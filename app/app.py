from flask import Flask, request, send_file, send_from_directory

import matplotlib.pyplot as plt
import io
import requests
import matplotlib.font_manager as fm
import datetime
from transformers import pipeline
import os
import json

HF_TOKEN = os.environ.get("HF_TOKEN")

app = Flask(__name__, static_folder="static")

import os
import requests

HF_TOKEN = os.environ.get("HF_TOKEN")  # set in HF Space secrets
HF_ENDPOINT_URL = "https://kz08yefzhrfxf9fy.us-east-1.aws.endpoints.huggingface.cloud"

def query_llama3(prompt):
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 150,
            "temperature": 0.7,
            "return_full_text": False
        }
    }

    response = requests.post(HF_ENDPOINT_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"Hugging Face endpoint error {response.status_code}: {response.text}")

    try:
        data = response.json()
    except Exception as e:
        raise Exception(f"Failed to parse JSON: {response.text}") from e

    # Expecting Hugging Face endpoint to return list of dicts with "generated_text"
    if isinstance(data, list) and "generated_text" in data[0]:
        return data[0]["generated_text"]

    raise Exception(f"Unexpected response format: {data}")



def generate_paper_tape(text, bell_enabled=False):    
    plt.rcParams['font.family'] = 'monospace'

    header = "#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#00,#00,#00,#00,#00,#00,#00,#00,#00,#00"
    footer = "#00,#00,#00,#00,#00,#00,#00,#00,#00,#00,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff,#ff"

    def parse_hex_code(hex_str):
        if hex_str.startswith("#"):
            try:
                return format(int(hex_str[1:], 16), '08b')
            except ValueError:
                raise ValueError(f"Invalid hex code: {hex_str}")
        return None

    def convert_to_binary(char):
        return format(ord(char), '08b')

    def get_visual_char(c):
        if isinstance(c, str) and len(c) == 1:
            code = ord(c)
            if 0x20 <= code <= 0x7E:
                return c  # printable ASCII
            else:
                return "."  # control character placeholder
        return c

    header_binary = [parse_hex_code(x) for x in header.split(",")]
    message_binary = [convert_to_binary(char) for char in text]

    bell_sequence = []
    bell_visuals = []
    if bell_enabled:
        for c in [chr(0x00), chr(0x00), chr(0x07)]:
            bell_sequence.append(convert_to_binary(c))
            bell_visuals.append(get_visual_char(c))

    footer_binary = [parse_hex_code(x) for x in footer.split(",")]

    full_binary = header_binary + message_binary + bell_sequence + footer_binary
    full_char_sources = header.split(",") + list(text) + bell_visuals + footer.split(",")

    visual_chars = []
    for char, code in zip(full_char_sources, full_binary):
        if len(char) == 1:
            visual_chars.append(get_visual_char(char))
        elif char.startswith("#"):
            try:
                val = int(char[1:], 16)
                if 0x00 <= val <= 0x1F:
                    visual_chars.append(chr(0x2400 + val))
                elif val == 0x7F:
                    visual_chars.append(chr(0x2421))
                elif val == 0xFF:
                    visual_chars.append("░")
                else:
                    visual_chars.append("�")
            except:
                visual_chars.append("?")

    ascii_punch_codes = [code for code in full_binary if code]    

    char_width = 0.7
    char_height = 8
    data_hole_radius = 0.25
    sprocket_hole_radius = 0.06
    sprocket_y = 4.5
    y_spacing_factor = 0.82

    fig, ax = plt.subplots(figsize=(len(ascii_punch_codes) * char_width, 2))
    ax.set_xlim(0, len(ascii_punch_codes) * char_width)
    ax.set_ylim(-1, char_height * y_spacing_factor)
    ax.set_aspect(1)

    ax.add_patch(plt.Rectangle((0, -1), len(ascii_punch_codes) * char_width, char_height * y_spacing_factor + 1, color="#FFCC66", ec="black"))

    for i, (char, code) in enumerate(zip(visual_chars, ascii_punch_codes)):    
        x_offset = i * char_width + char_width / 2
        for j, bit in enumerate(reversed(code)):
            if bit == '1':
                ax.add_patch(plt.Circle((x_offset, j * y_spacing_factor), data_hole_radius, color="black", fill=True))  
        ax.add_patch(plt.Circle((x_offset, sprocket_y * y_spacing_factor), sprocket_hole_radius, color="black", fill=True))
        ax.text(x_offset, -1.5, char, fontsize=14, fontname="monospace", ha="center", va="top", color="white", rotation=0)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', dpi=150, facecolor='#0f0f0f', transparent=False)
    img_io.seek(0)
    plt.close(fig)

    return img_io, len(ascii_punch_codes)

@app.route("/")
def root():
    return send_from_directory("static", "index.html")


@app.route('/generate_paper_tape', methods=['POST'])
def generate_tape():
    try:
        data = request.get_json()
        user_prompt = data.get("text", "")
        bell_enabled = data.get("bell", False)

        if not user_prompt:
            return "Error: No text provided", 400

        full_prompt = (
            "You are a Teletype Model 33 ASR from the year 1979, connected to a mainframe via serial cable. "
            "You respond in short bursts of uppercase text as if printed on a paper tape. "
            "Your language is efficient, mechanical, and dry. Limit output to a few words per line, like a real teletype outputting ASCII on paper tape. "
            "Avoid punctuation unless absolutely necessary. Never apologize or explain.\n\n"
            f"User: {user_prompt}\nTeletype:"
        )
        
        completion = query_llama3(full_prompt)

        completion = completion.replace(full_prompt, "").strip()
        
        jam_detected = len(completion) > 250
        if jam_detected:
            completion = completion[:250]

        img_io, punch_count = generate_paper_tape(completion, bell_enabled)

        response = send_file(img_io, mimetype='image/png')
        response.headers['X-Punch-Count'] = str(punch_count)
        response.headers["X-Jam"] = "1" if jam_detected else "0"
        return response
    except Exception as e:
        import traceback
        print("🔥 Full traceback:", flush=True)
        traceback.print_exc()
        return f"Server error: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)

