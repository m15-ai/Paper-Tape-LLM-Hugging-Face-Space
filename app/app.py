
from flask import Flask, request, send_file
import matplotlib.pyplot as plt
import io
import requests
import matplotlib.font_manager as fm
import datetime

app = Flask(__name__)

def generate_paper_tape(text, bell_enabled=False):    
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    for font in ["FreeMono", "Courier New"]:
        if font in available_fonts:
            plt.rcParams['font.family'] = font
            break

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
            if 0x00 <= code <= 0x1F:
                return chr(0x2400 + code)
            elif code == 0x7F:
                return chr(0x2421)
            else:
                return c
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
        ax.text(x_offset, -1.5, char, fontsize=14, fontname="FreeMono", ha="center", va="top", color="white", rotation=0)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)

    img_io = io.BytesIO()
    plt.savefig(img_io, format='png', bbox_inches='tight', dpi=150, facecolor='#0f0f0f', transparent=False)
    img_io.seek(0)
    plt.close(fig)

    return img_io, len(ascii_punch_codes)

@app.route('/generate_paper_tape', methods=['POST'])
def generate_tape():
    system_prompt = (
        "You are a Teletype Model 33 ASR from the year 1979, connected to a mainframe via serial cable. "
        "You respond in short bursts of uppercase text as if printed on a paper tape. "
        "Your language is efficient, mechanical, and dry. Limit output to a few words per line, like a real teletype outputting ASCII on paper tape. "
        "Avoid punctuation unless absolutely necessary. Never apologize or explain. "
    )

    data = request.get_json()
    user_prompt = data.get("text", "")
    bell_enabled = data.get("bell", False)

    if not user_prompt:
        return "Error: No text provided", 400

    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "qwen:0.5b",
        "prompt": user_prompt,
        "system": system_prompt,
        "options": {"temperature": 0.5},
        "stream": False
    })

    if not response.ok:
        return f"Ollama error: {response.text}", 500

    completion = response.json().get("response", "").strip()
    max_chars = 500
    if len(completion) > max_chars:
        completion = completion[:max_chars]
        jam_detected = True
    else:
        jam_detected = False

    img_io, punch_count = generate_paper_tape(completion, bell_enabled)

    ip_addr = request.remote_addr

    log_line = (
        f"[{datetime.datetime.now()}] "
        f"IP: {ip_addr} | MODEL: qwen:0.5b | "
        f"PROMPT: {user_prompt.strip()} || COMPLETION: {completion.strip().replace('\\n', ' ')[:500]}\n"
    )

    with open("usage.log", "a") as log_file:
        log_file.write(log_line)

    response = send_file(img_io, mimetype='image/png')
    response.headers['X-Punch-Count'] = str(punch_count)
    response.headers["X-Jam"] = "1" if jam_detected else "0"
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
