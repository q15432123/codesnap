"""CodeSnap — python run.py"""
if __name__ == "__main__":
    import uvicorn
    print("⚡ CodeSnap at http://127.0.0.1:8080")
    uvicorn.run("server:app", host="127.0.0.1", port=8080, reload=False)
