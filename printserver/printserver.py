#!/usr/bin/env python3
"""Mini serveur d'impression : upload d'une image -> lp (CUPS) -> Canon Selphy.

Usage :
    pip install flask
    PRINTER=Selphy python3 printserver.py

Puis ouvrir http://IP_DU_SERVEUR:3333
"""
import os
import subprocess
import tempfile

from flask import Flask, jsonify, request

PRINTER = os.environ.get("PRINTER", "Selphy")
PORT = int(os.environ.get("PORT", "3333"))
# Options CUPS (adapter avec : lpoptions -p Selphy -l)
LP_OPTIONS = os.environ.get("LP_OPTIONS", "media=Postcard fit-to-page").split()
ALLOWED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30 Mo

PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Impression Selphy</title>
<style>
 :root{color-scheme:dark}
 body{font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:2rem 1rem;
      background:#121212;color:#e6e6e6;min-height:100vh;box-sizing:border-box}
 img{max-width:100%;border-radius:8px;margin:1rem 0}
 button,input{font-size:1rem;padding:.6rem;width:100%;box-sizing:border-box;margin:.3rem 0;
      background:#1e1e1e;color:#e6e6e6;border:1px solid #333;border-radius:6px}
 button{background:#2d6cdf;border-color:#2d6cdf;color:#fff;cursor:pointer}
 button:hover{background:#3d7bef}
 #msg{margin-top:1rem;font-weight:600}
</style></head><body>
<h2>Imprimer sur la Selphy</h2>
<input type="file" id="file" accept="image/*">
<img id="preview" hidden>
<label>Copies <input type="number" id="copies" value="1" min="1" max="10"></label>
<button id="send">Imprimer</button>
<div id="msg"></div>
<script>
const f=document.getElementById('file'),p=document.getElementById('preview'),m=document.getElementById('msg');
f.onchange=()=>{if(f.files[0]){p.src=URL.createObjectURL(f.files[0]);p.hidden=false}};
document.getElementById('send').onclick=async()=>{
  if(!f.files[0]){m.textContent='Choisis une image.';return}
  const fd=new FormData();
  fd.append('image',f.files[0]);
  fd.append('copies',document.getElementById('copies').value);
  m.textContent='Envoi...';
  try{
    const r=await fetch('/print',{method:'POST',body:fd});
    const j=await r.json();
    m.textContent=r.ok?('OK : '+j.job):('Erreur : '+j.error);
  }catch(e){m.textContent='Erreur réseau'}
};
</script></body></html>"""


@app.get("/")
def index():
    return PAGE


@app.post("/print")
def print_image():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify(error="aucune image reçue"), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED:
        return jsonify(error=f"format non supporté ({ext})"), 400

    try:
        copies = max(1, min(10, int(request.form.get("copies", 1))))
    except ValueError:
        copies = 1

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        file.save(tmp)
        path = tmp.name

    cmd = ["lp", "-d", PRINTER, "-n", str(copies)]
    for opt in LP_OPTIONS:
        cmd += ["-o", opt]
    cmd.append(path)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    finally:
        # Les travaux CUPS copient le fichier à la soumission : on peut supprimer.
        try:
            os.remove(path)
        except OSError:
            pass

    if res.returncode != 0:
        return jsonify(error=res.stderr.strip() or "échec de lp"), 500
    return jsonify(job=res.stdout.strip())


@app.get("/status")
def status():
    res = subprocess.run(["lpstat", "-p", PRINTER, "-o"], capture_output=True, text=True)
    return jsonify(printer=PRINTER, output=res.stdout.strip(), error=res.stderr.strip())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
