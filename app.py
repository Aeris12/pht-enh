import base64
import os
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from google import genai
from google.genai import types

app = FastAPI(title="Photo Enhancer")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-image")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "12"))

PROMPT = """
Enhance the uploaded photograph while faithfully preserving the original image.
Keep the exact same scene, composition, people, identity, facial features, age,
pose, clothing, objects, object count, geometry, background, and framing.
Improve genuine photographic quality: recover natural sharpness and fine detail,
reduce blur, noise, compression artifacts, and faded contrast; improve exposure,
white balance, tonal range, and realistic textures subtly.
Do not add, remove, replace, invent, beautify, stylize, or redesign anything.
Do not change text, logos, facial structure, or any scene content.
The result must look like the same photograph captured with a better camera,
not a newly generated interpretation. Return one edited image only.
""".strip()

PAGE = r"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Photo Enhancer</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0b0c0e;color:#f5f5f5;font:16px system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:850px;margin:0 auto;padding:48px 20px}h1{font-size:clamp(32px,6vw,54px);margin:0 0 12px;letter-spacing:-1.5px}p{color:#aeb2ba;line-height:1.6}.panel{border:1px solid #303238;background:#121316;border-radius:20px;padding:24px;margin-top:28px}
.drop{display:block;border:1px dashed #555963;border-radius:14px;padding:28px;text-align:center;cursor:pointer}.drop input{display:none}.btn{border:0;border-radius:12px;padding:14px 22px;background:#f3f3f3;color:#101114;font-weight:700;cursor:pointer;width:100%;margin-top:16px;font-size:16px}.btn:disabled{opacity:.45;cursor:wait}
.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-top:22px}.images img{width:100%;height:auto;border-radius:12px;border:1px solid #333}.label{font-size:13px;color:#b6bbc4;margin:12px 0 8px}.status{white-space:pre-wrap;color:#c8cbd1;margin-top:16px;font-size:14px}.small{font-size:12px;color:#858b96}
</style></head><body><main>
<div class="small">PHOTO TOOLS</div><h1>Photo Enhancer</h1><p>Popraw jakość zdjęcia jednym kliknięciem. Scena i zawartość mają pozostać możliwie wierne oryginałowi.</p>
<section class="panel"><label class="drop"><input id="file" type="file" accept="image/png,image/jpeg,image/webp"><span id="droptext">Wybierz zdjęcie JPG, PNG lub WebP<br><span class="small">Maksymalnie 12 MB</span></span></label>
<div class="images" id="images"></div><button id="go" class="btn" disabled>Enhance</button><div id="status" class="status" role="status"></div>
</section><p class="small">Prototyp testowy. Wyniki generatywnej AI mogą zmieniać drobne szczegóły. Nie przesyłaj poufnych zdjęć.</p>
</main><script>
const file=document.getElementById('file'),go=document.getElementById('go'),status=document.getElementById('status'),images=document.getElementById('images'),droptext=document.getElementById('droptext');let selected;
file.addEventListener('change',()=>{selected=file.files[0];images.innerHTML='';status.textContent='';go.disabled=!selected;if(selected){droptext.textContent=selected.name;const url=URL.createObjectURL(selected);images.innerHTML='<div><div class="label">ORYGINAŁ</div><img src="'+url+'" alt="Oryginał"></div>'}});
go.addEventListener('click',async()=>{if(!selected)return;go.disabled=true;go.textContent='Przetwarzanie…';status.textContent='Wysyłanie zdjęcia do modelu AI…';try{const fd=new FormData();fd.append('file',selected);const r=await fetch('/api/enhance',{method:'POST',body:fd});if(!r.ok){let t=await r.text();throw new Error(t||'Błąd API');}const blob=await r.blob(),url=URL.createObjectURL(blob);const box=document.createElement('div');box.innerHTML='<div class="label">WYNIK</div>';const img=document.createElement('img');img.src=url;img.alt='Ulepszone zdjęcie';box.appendChild(img);const a=document.createElement('a');a.href=url;a.download='enhanced-photo.png';a.className='btn';a.style.display='block';a.style.textAlign='center';a.style.textDecoration='none';a.textContent='Pobierz wynik';box.appendChild(a);images.appendChild(box);status.textContent='Gotowe.';}catch(e){status.textContent='Nie udało się przetworzyć zdjęcia. '+e.message;}finally{go.disabled=!selected;go.textContent='Enhance'}});
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE

@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))}

@app.post("/api/enhance")
async def enhance(file: UploadFile = File(...)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API nie jest jeszcze skonfigurowane. Dodaj GEMINI_API_KEY w ustawieniach Render.")
    content_type = file.content_type or ""
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Dozwolone formaty: JPG, PNG, WebP.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Plik jest pusty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Plik jest większy niż {MAX_UPLOAD_MB} MB.")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                PROMPT,
                types.Part.from_bytes(data=data, mime_type=content_type),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in response.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                mime = part.inline_data.mime_type or "image/png"
                return Response(content=part.inline_data.data, media_type=mime,
                                headers={"Content-Disposition": 'inline; filename="enhanced-photo.png"'})
        raise HTTPException(status_code=502, detail="Model nie zwrócił obrazu. Sprawdź dostępność modelu i limity API.")
    except HTTPException:
        raise
    except Exception as exc:
        # Return a useful provider error without exposing credentials.
        message = str(exc).replace(api_key, "[UKRYTY KLUCZ API]") if api_key else str(exc)
        message = " ".join(message.split())[:700]
        app.logger.exception("Gemini request failed (model=%s, exception=%s)", MODEL, type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail=f"Dostawca AI zwrócił błąd ({type(exc).__name__}). Model: {MODEL}. Szczegóły: {message or 'brak szczegółów'}",
        ) from exc
