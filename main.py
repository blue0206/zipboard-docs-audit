import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.models.api import ApiError, ApiResponse
from src.api.endpoints import router

app = FastAPI()

# cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=router, prefix="/api/v1")

@app.exception_handler(ApiError)
async def api_exception_handler(req: Request, error: ApiError) -> ApiResponse:
    print("API Exception encountered: ", error)

    return ApiResponse(
        success=False,
        status_code=error.status_code,
        payload=error.payload
    )

@app.exception_handler(Exception)
async def global_exception_handler(req: Request, error: Exception) -> ApiResponse:
    print(f"An unhandled error occurred: {str(error)}")

    return ApiResponse(
        success=False,
        status_code=500,
        payload="Internal Server Error"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
