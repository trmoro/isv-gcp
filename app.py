import os
import time

# ISV scoring
from isv import isv

#Logger
from google.cloud import logging
logging_client = logging.Client()
log_name = "isv-log"
logger = logging_client.logger(log_name)

from mongo import get_mongo_db
client_db, db = get_mongo_db()
logger.log_text("ISV MongoDB connection opened")

#Import liftover, copy in /tmp for GCP
from liftover import ChainFile
os.system("cp -r chainfiles /tmp/chainfiles")
hg19to38_lifter = ChainFile("/tmp/chainfiles/hg19ToHg38.over.chain.gz","hg19","hg38")
hg38to19_lifter = ChainFile("/tmp/chainfiles/hg38ToHg19.over.chain.gz","hg38","hg19")

def hg19to38(chromosome : str,pos : int):
    l = hg19to38_lifter[chromosome][pos]
    if len(l) == 0:
        return pos
    else:
        return l[0][1]

def hg38to19(chromosome : str,pos : int):
    l = hg38to19_lifter[chromosome][pos]
    if len(l) == 0:
        return pos
    else:
        return l[0][1]
    
#Save to Mongo
def save(title,row):
	filt = {"title": title}
	db["isv"].replace_one(filt , row, upsert=True)
	logger.log_text(title + " ISV value updated !")

#Compute ISV on batch
def compute_isv(genomics_coordinates):

	#Convert to ISV queries format
	isv_queries = []
	for q in genomics_coordinates:

		#Convert to dup/del type
		dupdel = "DUP"
		if q["type"] == "loss":
			dupdel = "DEL"

		#Lift if hg19
		s = q["start"]
		e = q["end"]
		if q["ref"] == "hg19":
			s = hg19to38(q["chr"],q["start"])
			e = hg19to38(q["chr"],q["end"])

		#Add
		isv_queries.append([q["chr"],s,e,dupdel])

	#Compute
	results = isv(isv_queries)["ISV"]
	
	#Save all results
	for i in range(len(genomics_coordinates)):
		q = genomics_coordinates[i]
		title = q["ref"] + "-" + q["chr"] + "-" + str(q["start"]) + "-" + str(q["end"]) + "-" + str(q["type"])
		save(title, {"title": title, "score": results[i]})
		

##############Entrypoint for GCP
from flask import Flask
from flask import request

app = Flask(__name__)

@app.route("/single", methods=["GET"])
def single():
	t = time.time()
	logger.log_text("ISV Single")
	title = request.args.get("title")
	data = title.split("-")
	cnv = {"ref": data[0], "chr": data[1], "start": int(data[2]), "end": int(data[3]), "type": data[4]}
	compute_isv([cnv])
	logger.log_text(str(round(time.time() - t,2)) + " ISV CNV-Hub finished !")
	return {"text":"ISV Batch OK !"}

@app.route("/batch", methods=["GET"])
def batch():
	t = time.time()
	logger.log_text("ISV Batch")
	batch_id = request.args.get("batch-id")
	batch_data = db["cnvhub_batch"].find_one({'batchId':batch_id})["genomicCoordinates"]
	compute_isv(batch_data)
	logger.log_text(str(round(time.time() - t,2)) + " ISV CNV-Hub finished !")
	return {"text":"ISV Batch OK !"}

if __name__ == "__main__":
	app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))