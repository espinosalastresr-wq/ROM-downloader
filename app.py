from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.responses import StreamingResponse
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
    progress { width: 100%; margin-top: 1em; height: 20px; }
    #progress[value]::-webkit-progress-bar { background-color: #eee; }
    #progress[value]::-webkit-progress-value { background-color: green; }
    #progress.error::-webkit-progress-value { background-color: red; }
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
    form.onsubmit = (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const url = data.get("url");
      const progress = document.getElementById("progress");
      const result = document.getElementById("result");
      progress.value = 0;
      progress.style.display = "block";
      progress.classList.remove("error");
      result.innerHTML = "";

      const evtSource = new EventSource("/download_and_extract?url=" + encodeURIComponent(url));
      evtSource.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.progress !== undefined) {
          progress.value = msg.progress;
        }
        if (msg.done) {
          evtSource.close();
          progress.value = 100;
          result.innerHTML = '<p>Descarga completa ✅</p><a href="/get_boot">Descargar boot.img</a>';
        }
        if (msg.error) {
          evtSource.close();
          progress.classList.add("error");
          result.innerHTML = "<p style='color:red'>" + msg.error + "</p>";
        }
      };
      evtSource.onerror = () => {
        evtSource.close();
        progress.classList.add("error");
        result.innerHTML = "<p style='color:red'>❌ Proceso interrumpido</p>";
      };
    };
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.get("/download_and_extract")
def download_and_extract(url: str):
    def event_stream():
        # limpiar restos anteriores
        if os.path.exists("firmware"):
            shutil.rmtree("firmware")
        for f in ["firmware.tgz", "firmware.zip", "boot.img"]:
            if os.path.exists(f):
                os.remove(f)

        local_file = "firmware.tgz" if url.endswith(".tgz") else "firmware.zip"

        try:
            with requests.get(url, stream=True, timeout=30) as r:
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(local_file, "wb") as f:
                    for chunk in r.iter_content(1024*1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = int(downloaded * 100 / total)
                            yield f"data: {{\"progress\": {percent}}}\n\n"

            # Extraer firmware
            os.makedirs("firmware", exist_ok=True)
            if local_file.endswith(".tgz"):
                with tarfile.open(local_file, "r:gz") as tar:
                    tar.extractall("firmware")
            else:
                with zipfile.ZipFile(local_file, "r") as z:
                    z.extractall("firmware")

            # Buscar boot.img
            boot_path = None
            for root, _, files in os.walk("firmware"):
                if "boot.img" in files:
                    boot_path = os.path.join(root, "boot.img")
                    shutil.copy(boot_path, "boot.img")
                    break

            if not boot_path:
                yield 'data: {"error": "boot.img no encontrado"}\n\n'
                return

            yield 'data: {"done": true}\n\n'

        except Exception as e:
            yield f'data: {{"error": "Error: {str(e)}"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/get_boot")
def get_boot():
    if os.path.exists("boot.img"):
        return FileResponse("boot.img", filename="boot.img")
    return {"error": "boot.img aún no generado"}
