from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Colf API", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head>
            <title>Colf API</title>
        </head>
        <body>
            <h1>Welcome to Colf API</h1>
            <p>Your FastAPI application is running!</p>
        </body>
    </html>
    """


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "message": "API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)