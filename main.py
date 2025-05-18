from fastapi import FastAPI
import uvicorn

app = FastAPI(title="ChatBot")

@app.get("/")
async def root():
    return {"message": "Welcome to the ChatBot API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 