FROM python:3.11-slim

# Before: no container entrypoint; After: Cloud Run image runs the bot via main.py
WORKDIR /app

COPY chef/chefmain/requirements.txt /app/chef/chefmain/requirements.txt
RUN pip install --no-cache-dir -r /app/chef/chefmain/requirements.txt

COPY . /app

# Before: no default port; After: container listens on Cloud Run's expected port
ENV PORT=8080

EXPOSE 8080

CMD ["python", "chef/chefmain/main.py"]
