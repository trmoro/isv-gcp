FROM python:3.8-slim

# Copy data
COPY . ./

#Permission on chainfiles
RUN chmod -R 755 ./chainfiles

# Install Python3 requirements packages
RUN pip install -r requirements.txt

#Set Entrypoint for GCP
ENTRYPOINT ["python"]
CMD ["app.py"]
