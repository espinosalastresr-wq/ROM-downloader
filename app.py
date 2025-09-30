from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
import requests, tarfile, zipfile, os, shutil

app = FastAPI()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Extractor boot.img</title>
  <style>
    body { font-family: sans-serif; margin: 2em; }
    input[type=text] { width: 60%; padding: 8px; }
    button { padding: 8px 16px; margin-left: 8px; }
    progress { width: 100%; margin-top: 1em; }
  </style>
</head>
<body>
  <h2>Extraer boot.img desde firmware Xiaomi</h2>
  <form id="form">
    <input type="text" name="url" placeholder="Pega la URL del firmware oficial" required>
    <button type="submit">Descargar y extraer</button>
  </form>
  <progress id="progress" value="0" max="100" style="display:none;"></progress>
  <div id="result"></div>

  <script>
    const form = document.getElementById("form");
    form.onsubmit = async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      document.getElementById("progress").style.display = "block";
      document.getElementById("progress").value = 10;
      const res = await fetch("/extract_boot", { method: "POST", body: data });
      if (res.headers.get("content-type").includes("application/json")) {
        const err = await res.json();
        document.getElementById("result").innerHTML = "<p style='color:red'>" + err.error + "</p>";
      } else {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "boot.img";
        a.click();
        document.getElementById("result").innerHTML = "<p>Descarga completa ✅</p>";
      }
      document.getElementById("progress").value = 100;
    };
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE

@app.post("/extract_boot")
def extract_boot(url: str = Form(...)):
    # limpiar restos de ejecuciones anteriores
    if os.path.exists("firmware"):
        shutil.rmtree("firmware")
    if os.path.exists("firmware.tgz"):
        os.remove("firmware.tgz")
    if os.path.exists("firmware.zip"):
        os.remove("firmware.zip")

    # descargar firmware
    local_file = "firmware.tgz" if url.endswith(".tgz") else "firmware.zip"
    with requests.get(url, stream=True) as r:
        with open(local_file, "wb") as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)

    # extraer según tipo
    os.makedirs("firmware", exist_ok=True)
    if local_file.endswith(".tgz"):
        with tarfile.open(local_file, "r:gz") as tar:
            tar.extractall("firmware")
    elif local_file.endswith(".zip"):
        with zipfile.ZipFile(local_file, "r") as z:
            z.extractall("firmware")

    # buscar boot.img
    boot_path = None
    for root, dirs, files in os.walk("firmware"):
        if "boot.img" in files:
            boot_path = os.path.join(root, "boot.img")
            break

    if not boot_path:
        return {"error": "boot.img no encontrado"}

    return FileResponse(boot_path, filename="boot.img")
