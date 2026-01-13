from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/test")
async def test():
    return JSONResponse(content={"status": "ok"})

@app.get("/regions")
async def test_regions():
    data = [
        {"id": 1, "name": "Астана", "code": "75", "region_type": "CITY"},
        {"id": 2, "name": "Алматы", "code": "19", "region_type": "CITY"}
    ]
    return JSONResponse(content=data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
