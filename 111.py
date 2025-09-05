import os
import time
import subprocess
import re
import textwrap
from pathlib import Path
from zipfile import ZipFile
from flask import Flask, request, render_template_string, send_file, abort
from yt_dlp import YoutubeDL
from PIL import Image, ImageDraw, ImageFont


# --- ffmpeg PATH ---
os.environ["PATH"] = r"C:\ffmpeg\bin;" + os.environ.get("PATH", "")

app = Flask(__name__)
BASE_OUTDIR = Path("web_downloads")
BASE_OUTDIR.mkdir(parents=True, exist_ok=True)

# ===== Output Config =====
TARGET_W   = 1080
TARGET_H   = 1920
TEXT_COLOR = (0, 0, 0, 255)   # ฟอนต์สีดำ
FONT_PATH  = "KanchaStay.ttf"  # ฟอนต์ในโฟลเดอร์ fonts

# ===== Default Layout Config =====
LINE_SPACING    = 12   # ระยะห่างบรรทัด (px)
BOTTOM_MARGIN   = 70   # ระยะห่างจากขอบล่าง (px)
SIDE_MARGIN     = 120  # ระยะห่างจากขอบซ้ายขวา
MAX_FONT_SIZE   = 100
MIN_FONT_SIZE   = 30

# --- HTML Form ---
HTML = """
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=0.9, maximum-scale=0.9, user-scalable=no">
<title>IG Downloader</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:100%;margin:0;padding:0.5rem;background:#fafafa;font-size:14px;}
  h1{font-size:18px;text-align:center;margin:0.5rem 0;}
  .card{border:1px solid #ddd;border-radius:12px;padding:12px;box-shadow:0 1px 6px rgba(0,0,0,.05);background:white;}
  textarea,input[type=text],input[type=file],select{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px;font-size:14px;}
  input[type=range]{width:100%}
  .row{display:grid;gap:8px}
  .row-two{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
  .label-inline{display:flex;gap:6px;align-items:center;font-size:14px}
  .btn{background:#111;color:#fff;border:none;border-radius:8px;padding:10px 14px;font-size:14px;cursor:pointer;width:100%;}
  #preview{margin-top:10px;width:70%;max-height:30vh;object-fit:contain;display:block;margin-left:auto;margin-right:auto;border:none;border-radius:0;filter: drop-shadow(0 4px 8px rgba(0,0,0,0.4));background:transparent;}
  @media(max-width:600px){.row-two{grid-template-columns:1fr;}}
</style>

<h1>Instagram Downloader</h1>
<div class="card">
  <form method="post" action="/download" enctype="multipart/form-data" class="row" id="mainForm" onsubmit="setTimeout(()=>this.reset(),500)">

    <label>ลิงก์ IG (บรรทัดละ 1) หรือ เลือกไฟล์วิดีโอจากเครื่อง</label>
    <textarea name="urls" rows="1" placeholder="https://www.instagram.com/reel/......./"></textarea>
    <input type="file" name="upload_file" accept="video/*">

    <div class="row-two">
      <div>
        <label>ข้อความบนคลิป (หลายบรรทัดได้)</label>
        <textarea name="header_text" rows="2" placeholder="ใส่ข้อความ" maxlength="200"></textarea>
      </div>
      <div>
        <label>ลายน้ำ (Watermark)</label>
        <select name="watermark_text">
          <option value="">-- ไม่ใส่ --</option>
          <option value="Dewyรีวิว">Dewyรีวิว</option>
          <option value="พิกัดจัดให้">พิกัดจัดให้</option>
          <option value="จิ้มลิงก์สิคะ">จิ้มลิงก์สิคะ</option>
          <option value="สู้ๆนะ">สู้ๆนะ</option>
        </select>
      </div>
    </div>

    <div class="label-inline"><label>ความสูงขอบขาว </label><output id="white_val">30%</output></div>
    <input type="range" name="white_bar" min="20" max="40" step="2" value="30" oninput="white_val.value = this.value + '%'">

    <div class="label-inline"><label>เลื่อนคลิปลง </label><output id="shift_val">10%</output></div>
    <input type="range" name="shift_down" min="0" max="40" step="2" value="10" oninput="shift_val.value = this.value + '%'">

    <div class="label-inline"><label>ระยะห่างบรรทัด </label><output id="line_val">12px</output></div>
    <input type="range" name="line_spacing" min="1" max="60" step="2" value="12" oninput="line_val.value = this.value + 'px'">

    <div class="label-inline"><label>ระยะห่างจากขอบล่าง </label><output id="bottom_val">70px</output></div>
    <input type="range" name="bottom_margin" min="10" max="200" step="5" value="70" oninput="bottom_val.value = this.value + 'px'">

    <div class="label-inline"><label>ความเร็วคลิป </label><output id="speed_val">1.0x</output></div>
    <input type="range" name="playback_speed" min="0.8" max="1.5" step="0.1" value="1.0" oninput="speed_val.value = this.value + 'x'">

    <button class="btn" type="submit" id="submitBtn">ตกลง (ดาวน์โหลด/อัปโหลด & ตัดต่อ)</button>

  </form>

<img id="preview" src="" alt="Preview จะโชว์ตรงนี้">

<div id="loadingOverlay" style="display:none;">
  <div class="spinner"></div>
  <div>⏳ กำลังประมวลผล... กรุณารอสักครู่</div>
</div>

<script>
const form = document.getElementById("mainForm");
const previewImg = document.getElementById("preview");
const submitBtn = document.getElementById("submitBtn");

// ✅ โหลด preview
function updatePreview(){
  let data = new FormData(form);

  // 🚫 ปิดปุ่มไว้ก่อน
  submitBtn.disabled = true;
  submitBtn.style.background = "#888";

  fetch("/preview", {method:"POST", body:data})
    .then(r => {
      if(!r.ok) throw new Error("Preview error");
      return r.blob();
    })
    .then(b => { 
      previewImg.src = URL.createObjectURL(b); 
      // ✅ เปิดปุ่มเมื่อโหลดเสร็จ
      submitBtn.disabled = false;
      submitBtn.style.background = "#111";
    })
    .catch(err => {
      console.error("Preview error:", err);
      // ❌ ไม่ต้องแจ้ง error แค่ปุ่มยังเทาไว้
    });
}

document.querySelectorAll("textarea, input[type=text], select, input[type=range], input[type=file]")
  .forEach(el => el.addEventListener("input", updatePreview));


// ✅ จัดการ Download
form.addEventListener("submit", (e)=>{
  e.preventDefault();
  const data = new FormData(form);

  document.getElementById("loadingOverlay").style.display="flex";

  fetch("/download", {method:"POST", body:data})
    .then(async resp=>{
      if(resp.status === 429){
        alert("⚠️ มีงานกำลังทำอยู่ กรุณารอสักครู่");
        document.getElementById("loadingOverlay").style.display="none";
        return;
      }
      if(!resp.ok){
        alert("❌ เกิดข้อผิดพลาด");
        document.getElementById("loadingOverlay").style.display="none";
        return;
      }

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = resp.headers.get("Content-Disposition")?.split("filename=")[1] || "output.mp4";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      document.getElementById("loadingOverlay").style.display="none";
    })
    .catch(err=>{
      console.error(err);
      alert("❌ เกิดข้อผิดพลาด");
      document.getElementById("loadingOverlay").style.display="none";
    });
});
</script>



"""

# ---------------- Utils ----------------
def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:150]

def get_ydl_opts(outdir: Path):
    return {
        "outtmpl": str(outdir / "%(uploader)s_%(id)s_%(title)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "cookiefile": "cookies.txt",
    }

# ---------------- Text & FFmpeg ----------------
def draw_bottom_text(draw, text, font_path, box_w, box_h,
                     bottom_margin=BOTTOM_MARGIN,
                     side_margin=SIDE_MARGIN,
                     line_spacing=LINE_SPACING,
                     max_font=MAX_FONT_SIZE,
                     min_font=MIN_FONT_SIZE):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return

    usable_width = box_w - side_margin * 2
    sizes = []
    heights = []

    for ln in lines:
        # เริ่มจากฟอนต์ใหญ่สุด
        font = ImageFont.truetype(font_path, max_font)
        bbox = draw.textbbox((0, 0), ln, font=font)
        text_w = bbox[2] - bbox[0]

        if text_w == 0:
            sizes.append(min_font)
            heights.append(0)
            continue

        # scale factor ปรับให้ข้อความเต็มความกว้าง usable_width
        scale = usable_width / text_w
        new_size = int(max_font * scale)

        # จำกัดไม่ให้เล็กกว่า min_font หรือใหญ่กว่า max_font
        new_size = max(min_font, min(max_font, new_size))

        sizes.append(new_size)
        font_resized = ImageFont.truetype(font_path, new_size)
        h = draw.textbbox((0, 0), ln, font=font_resized)[3]
        heights.append(h)

    total_h = sum(heights) + (len(lines) - 1) * line_spacing
    y = box_h - bottom_margin - total_h

    # วาดข้อความแต่ละบรรทัด
    for ln, size, h in zip(lines, sizes, heights):
        font = ImageFont.truetype(font_path, size)
        bbox = draw.textbbox((0, 0), ln, font=font)
        text_w = bbox[2] - bbox[0]
        x = (box_w - text_w) // 2
        draw.text((x, y), ln, font=font, fill=TEXT_COLOR)
        y += h + line_spacing


def add_watermark_text(draw, text, font_path, box_w, box_h,
                       margin_left=50, opacity=77, font_size=35):
    if not text: return
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.textbbox((0,0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = margin_left; y = (box_h - th) // 2
    fill = (255, 255, 255, opacity)
    draw.text((x, y), text, font=font, fill=fill)

def preview_frame(video_path: Path, header_text: str, white_bar: int, shift_down: int,
                  watermark_text: str = "", line_spacing:int=LINE_SPACING,
                  bottom_margin:int=BOTTOM_MARGIN, playback_speed:float=1.0):

    # ✅ ใช้ขนาดเดียวกับ process_with_ffmpeg
    TARGET_W, TARGET_H = 1080, 1920

    tmp_frame = video_path.with_suffix(".tmp.jpg")
    shift_px = int(TARGET_H * shift_down / 100)
    filter_complex = (
        f"scale=w={TARGET_W}:h={TARGET_H},setpts={1.0/playback_speed}*PTS[vs];"
        f"[vs]pad={TARGET_W}:{TARGET_H+shift_px}:0:{shift_px}:black[vp];"
        f"[vp]crop={TARGET_W}:{TARGET_H}:0:0"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", filter_complex,
        "-frames:v", "1", "-update", "1", str(tmp_frame)
    ]
    subprocess.run(cmd, check=True)

    base = Image.open(tmp_frame).convert("RGBA")
    W, H = base.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    white_h = int(H * (white_bar / 100))
    draw.rectangle([0, 0, W, white_h], fill=(255, 255, 255, 255))

    if header_text:
        draw_bottom_text(draw, header_text, FONT_PATH, W, white_h,
                         bottom_margin=bottom_margin, line_spacing=line_spacing)
    if watermark_text:
        add_watermark_text(draw, watermark_text, FONT_PATH, W, H)

    result = Image.alpha_composite(base, overlay)
    out = video_path.with_name("preview.png")
    result.save(out)
    return out


def get_video_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error","-show_entries", "format=duration","-of", "default=noprint_wrappers=1:nokey=1",str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try: return float(result.stdout.strip())
    except: return 0.0

def process_with_ffmpeg(inp: Path, outp: Path, header_text: str,
                        white_bar_pct: int = 30, shift_down_pct: int = 20,
                        watermark_text: str = "", line_spacing:int=LINE_SPACING,
                        bottom_margin:int=BOTTOM_MARGIN, playback_speed:float=1.0):

    TARGET_W, TARGET_H = 1080, 1920

    white_h = int(TARGET_H * (white_bar_pct / 100.0))
    duration = get_video_duration(inp)

    layers = []
    idx = 1

    # ---------- Header ----------
    if header_text:
        header_png = outp.with_name("header.png")
        dummy = Image.new("RGBA", (TARGET_W, white_h), (255,255,255,0))
        d = ImageDraw.Draw(dummy)
        draw_bottom_text(d, header_text, FONT_PATH, TARGET_W, white_h,
                         bottom_margin=bottom_margin, line_spacing=line_spacing)
        dummy.save(header_png)
        layers.append(f"-i {header_png}")

    # ---------- Watermark ----------
    if watermark_text:
        wm_png = outp.with_name("watermark.png")
        dummy = Image.new("RGBA", (TARGET_W, TARGET_H), (0,0,0,0))
        d = ImageDraw.Draw(dummy)
        add_watermark_text(d, watermark_text, FONT_PATH, TARGET_W, TARGET_H)
        dummy.save(wm_png)
        layers.append(f"-i {wm_png}")

    # ---------- Last text ----------
    last_text_png = outp.with_name("last_text.png")
    dummy = Image.new("RGBA", (TARGET_W, TARGET_H), (0,0,0,0))
    d = ImageDraw.Draw(dummy)
    font = ImageFont.truetype(FONT_PATH, 48)

    msg = "พิกัดสินค้าในคอมเมนต์เลยนะ"
    bbox = d.textbbox((0,0), msg, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]

    x = (TARGET_W - tw) // 2
    y = TARGET_H - int(TARGET_H * 0.15) - th
    d.text((x, y), msg, font=font, fill=(255,255,255,255))
    dummy.save(last_text_png)
    layers.append(f"-i {last_text_png}")

    # ---------- Base filter ----------
    filter_complex = (
        f"[0:v]setpts={1.0/playback_speed}*PTS,"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawbox=x=0:y=0:w={TARGET_W}:h={white_h}:color=white:t=fill[vout]"
    )

    overlays = "vout"
    if header_text:
        filter_complex += f";[{overlays}][{idx}:v]overlay=(W-w)/2:0[vh]"
        overlays = "vh"; idx += 1

    if watermark_text:
        wm_start = duration * 0.5
        filter_complex += f";[{overlays}][{idx}:v]overlay=30:H-h-30:enable='between(t,{wm_start},{duration})'[vw]"
        overlays = "vw"; idx += 1

    filter_complex += f";[{overlays}][{idx}:v]overlay=0:0:enable='between(t,{duration-2},{duration})'[vout]"

    # ---------- Run ffmpeg ----------
    cmd = ["ffmpeg","-y","-i", str(inp)]
    for l in layers:
        cmd.extend(l.split())
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "0:a?",
        "-filter:a", f"atempo={min(max(playback_speed,0.5),2.0)}",
        "-c:v","libx264",
        "-preset","veryfast",   # encode ช้ากว่า แต่คม
        "-crf","18",        # ชัดใกล้เคียงต้นฉบับ
        "-c:a","aac","-b:a","128k",
        "-threads","2",
        "-movflags","+faststart", str(outp),
    ])
    subprocess.run(cmd, check=True)







# --------------- Routes ---------------
# --------------- Routes ---------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML)


# ✅ PREVIEW
@app.route("/preview", methods=["POST"])
def preview_route():
    try:
        urls_raw = (request.form.get("urls") or "").strip()
        upload_file = request.files.get("upload_file")

        # --- ใช้ไฟล์ชั่วคราว (ไม่ต้องโหลดใหม่ทุกครั้ง)
        cache_dir = BASE_OUTDIR / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        video = cache_dir / "preview.mp4"

        if upload_file:
            # ถ้ามีอัปโหลดใหม่ → เขียนทับไฟล์ cache
            upload_file.save(video)
        elif urls_raw and not video.exists():
            # ถ้ามีลิงก์และยังไม่มี cache → โหลดครั้งเดียว
            url = urls_raw.splitlines()[0].strip()
            ydl_opts = get_ydl_opts(cache_dir)
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            raw_files = sorted(cache_dir.glob("*.*"))
            if not raw_files:
                abort(500, "โหลดวิดีโอไม่สำเร็จ")
            raw_files[0].rename(video)

        if not video.exists():
            abort(400, "ไม่มีไฟล์พรีวิว")

        # --- ข้อมูลฟอร์ม
        header_text = (request.form.get("header_text") or "").strip()
        watermark_text = (request.form.get("watermark_text") or "").strip()
        white_bar = int(request.form.get("white_bar", 30))
        shift_down = int(request.form.get("shift_down", 20))
        line_spacing = int(request.form.get("line_spacing", LINE_SPACING))
        bottom_margin = int(request.form.get("bottom_margin", BOTTOM_MARGIN))
        playback_speed = float(request.form.get("playback_speed", 1.0))

        # --- ใช้แค่เฟรมแรก ไม่ encode ทั้งไฟล์
        out = preview_frame(video, header_text, white_bar, shift_down,
                            watermark_text, line_spacing, bottom_margin,
                            playback_speed)
        return send_file(out, mimetype="image/png")

    except Exception as e:
        app.logger.error(f"[Preview Error] {e}")
        return jsonify({"error": str(e)}), 500



# ✅ DOWNLOAD
@app.route("/download", methods=["POST"])
def download_route():
    try:
        urls_raw = ""
        upload_file = None

        if request.is_json:
            data = request.get_json(silent=True) or {}
            urls_raw = (data.get("urls") or "").strip()
        else:
            urls_raw = (request.form.get("urls") or "").strip()
            upload_file = request.files.get("upload_file")

        header_text = (request.form.get("header_text") or "").strip()
        watermark_text = (request.form.get("watermark_text") or "").strip()
        white_bar = int(request.form.get("white_bar", 30))
        shift_down = int(request.form.get("shift_down", 20))
        line_spacing = int(request.form.get("line_spacing", LINE_SPACING))
        bottom_margin = int(request.form.get("bottom_margin", BOTTOM_MARGIN))
        playback_speed = float(request.form.get("playback_speed", 1.0))

        urls = [u.strip() for u in urls_raw.splitlines() if u.strip()]
        stamp = time.strftime("%Y%m%d_%H%M%S")
        outdir = BASE_OUTDIR / stamp
        rawdir, prodir = outdir / "raw", outdir / "processed"
        rawdir.mkdir(parents=True, exist_ok=True)
        prodir.mkdir(parents=True, exist_ok=True)

        raw_files = []
        if urls:
            ydl_opts = get_ydl_opts(rawdir)
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(urls)
            except Exception as e:
                abort(500, f"โหลดวิดีโอไม่สำเร็จ: {e}")
            raw_files = [p for p in rawdir.glob("*.*")
                         if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]
        if upload_file:
            local_file = rawdir / safe_name(upload_file.filename)
            upload_file.save(local_file)
            raw_files.append(local_file)

        if not raw_files:
            abort(500, "ไม่มีวิดีโอให้ตัดต่อ")

        processed = []
        for f in raw_files:
            outp = prodir / (safe_name(f.stem) + "_edited.mp4")
            process_with_ffmpeg(f, outp, header_text, white_bar, shift_down,
                                watermark_text, line_spacing, bottom_margin,
                                playback_speed)
            if outp.exists() and outp.stat().st_size > 0:
                processed.append(outp)

        if not processed:
            abort(500, "ตัดต่อไม่สำเร็จทุกไฟล์")
        if len(processed) == 1:
            return send_file(processed[0], as_attachment=True,
                             download_name=processed[0].name)

        zip_path = prodir.with_suffix(".zip")
        with ZipFile(zip_path, "w") as z:
            for p in processed:
                z.write(p, arcname=p.name)
        return send_file(zip_path, as_attachment=True,
                         download_name=zip_path.name)

    except Exception as e:
        app.logger.error(f"[Download Error] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
