from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Server Fujitsu Subdomain</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f0f0f0;
            }
            .box {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #2c3e50; }
            .success { color: #27ae60; font-weight: bold; }
            .info { color: #3498db; }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>🚀 Server Running!</h1>
            <p class="info">📡 Subdomain: test.logicencoder.com</p>
            <p class="info">🔒 SSL: Cloudflare handles it automatically</p>
            <hr>
            <p><strong>Server Info:</strong></p>
            <ul>
                <li>HTTPS enabled automatically</li>
            </ul>
        </div>
    </body>
    </html>
    """

@app.get("/api/test")
async def api_test():
    return {
        "status": "ok",
        "message": "API endpoint working",
        # "port": 8020,
        "subdomain": "test.logicencoder.com"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8020)
