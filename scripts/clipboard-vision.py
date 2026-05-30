"""剪切板识图：读取剪切板图片 → 阿里 DashScope Qwen 视觉 → 输出描述"""
import base64, io, json, sys, urllib.request
from PIL import ImageGrab
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "sk-20ba89c16bce4fbc8f30038b05147265"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

img = ImageGrab.grabclipboard()
if img is None:
    print("剪切板无图片")
    sys.exit(1)

buf = io.BytesIO()
img.convert("RGB").save(buf, "JPEG", quality=85)
b64 = base64.b64encode(buf.getvalue()).decode()

prompt = sys.argv[1] if len(sys.argv) > 1 else "请详细描述这张图片的内容"
body = json.dumps({
    "model": "qwen-vl-max",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": prompt}
        ]
    }]
}).encode()

req = urllib.request.Request(API_URL, data=body, headers={
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
})
resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
print(resp["choices"][0]["message"]["content"])
