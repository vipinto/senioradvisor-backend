import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8001')}"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
