# import the necessary packages
from imutils.video import VideoStream
from imutils.video import FPS
import numpy as np
import argparse
import imutils
import pickle
import time
import cv2
import os
import xlwt
from xlwt import Workbook 
import datetime
 
# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-d", "--detector", required=True,
	help="path to OpenCV's deep learning face detector")
ap.add_argument("-m", "--embedding-model", required=True,
	help="path to OpenCV's deep learning face embedding model")
ap.add_argument("-r", "--recognizer", required=True,
	help="path to model trained to recognize faces")
ap.add_argument("-l", "--le", required=True,
	help="path to label encoder")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
	help="minimum probability to filter weak detections")
args = vars(ap.parse_args())


# load our serialized face detector from disk
print("[INFO] loading face detector....")
protoPath = os.path.sep.join([args["detector"], "deploy.prototxt"])
modelPath = os.path.sep.join([args["detector"], "res10_300x300_ssd_iter_140000.caffemodel"])
detector = cv2.dnn.readNetFromCaffe(protoPath, modelPath)

# load our serialized face embedding model from disk
print("[INFO] loading face embedding model....")
embedder = cv2.dnn.readNetFromTorch(args["embedding_model"])

# load the actual face recognition model along with the label encoder
recognizer = pickle.loads(open(args["recognizer"], "rb").read())
le = pickle.loads(open(args["le"], "rb").read())

# initialize our list for the presentees
print("[INFO] initialize our Dictionary for presentees....")
attendance = {}
present = []
for i,e in enumerate(le.classes_):
	attendance.update({e : "absent"})

# Creating workbook and adding sheet into it for the attendance
wb = Workbook()
attendanceSheet = wb.add_sheet('Attendance Sheet')

# initialize the video stream, then allow the camera sensor to warm up
print("[INFO] starting video stream....")
vs = VideoStream(src=0).start()
time.sleep(2.0)

# start the FPS throughput estimator
fps = FPS().start()

# loop over the frames from the video file stream
while True:
	# grab the frame from the threaded video stream
	frame = vs.read()

	# resize the frame to have a width of 600 pixels and then grab the image dimensions
	frame = imutils.resize(frame, width=600)
	(h, w) = frame.shape[:2]

	# construct the blob for the frame
	imageBlob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=False, crop=False)

	# apply Opencv's deep learning based face detector to localize faces in the input image
	detector.setInput(imageBlob)
	detections = detector.forward()

	# loop over the detections
	for i in range (0, detections.shape[2]):
		# extract the confidence associated with the prediction
		confidence = detections[0, 0, i, 2]

		# filter out weak detections
		if confidence > args["confidence"]:
			# compute (x,y) coordinate of the bounding box
			box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
			(startX, startY, endX, endY) = box.astype("int")

			# extract the face ROI
			face = frame[startY:endY, startX:endX]
			(fh, fw) = face.shape[:2]

			# ensure the face width and height are sufficiently large
			if fw < 20 or fh < 20:
				continue

			# construct the blob for the face ROI, then pass the blob through our face embedding model to
			# obtain 128-d embedding of the face
			faceBlob = cv2.dnn.blobFromImage(face, 1.0/255, (96,96), (0, 0, 0), swapRB=True, crop=False)
			embedder.setInput(faceBlob)
			vec =  embedder.forward()

			# perform classfication to recognize the face
			preds = recognizer.predict_proba(vec)[0]
			j = np.argmax(preds)
			proba = preds[j]
			name = le.classes_[j]

			# adding the presentees
			present.append(name)

			# draw the bounding box of the face along with the associated probability
			text = "{}: {:.2f}%".format(name, proba * 100)
			y = startY - 10 if startY - 10 > 10 else startY + 10
			cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 0, 255), 2)
			cv2.putText(frame, text, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

	# update the FPS counter
	fps.update()

	# show the output frame
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF

	# if the 'q' key is pressed, break the loop
	if key == ord("q"):
		break

# stop the timer and display FPS information
fps.stop()
print("[INFO] elasped time: {:.2f}".format(fps.elapsed()))
print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

# print the attendance and output it in an excel file
for name in present:
	attendance[name] = 'present'
i=0
attendanceSheet.write(i, 0, 'Students')
attendanceSheet.write(i, 1, 'Attendance')
for name, status in attendance.items():
	attendanceSheet.write(i+1, 0, name)
	attendanceSheet.write(i+1, 1, status)
	i+=1
now = datetime.datetime.now()
date = now.strftime("%Y-%m-%d")
wb.save('Attendance_of_' + date + '.xls')
print(attendance)

# cleaning up
cv2.destroyAllWindows()
vs.stop()
