#!/usr/bin/env python3

import numpy as np
import cv2
import dlib
import argparse
import sys
import os.path
import math
import tkinter as tk
import tkinter.font as tkFont

from imutils.video import VideoStream
from common import draw_str
from utils.centroidtracker import CentroidTracker
from utils.trackableobject import TrackableObject
from multiprocessing import Process, Manager, Value, Event, Pipe

evt = Event()
process = None

root = None
tkframe = None
parent_conn = None
fullscreen = False

font_size = -24

status_dfont = None
status_label = None

count_dfont = None
count_label = None

quantity_dfont = None
quantity_label = None

max_label = None
max_amount = 0

dcount = 0
button_quit = None
   
inpWidth = 416   
inpHeight = 416
confThreshold = 0.6  
nmsThreshold = 0.4

writer = None
W = None
H = None

ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
trackers = []
trackableObjects = {}

totalDown = 0
totalUp = 0

modelConfiguration = "yolov3.cfg"
modelWeights = "yolov3.weights"

net = cv2.dnn.readNetFromDarknet(modelConfiguration, modelWeights)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)

def stop_counting():
    evt.set()
    process.terminate()
    cv2.destroyAllWindows()
    root.quit()
    root.destroy()

def toggle_fullscreen(event=None):
    global root
    global fullscreen

    fullscreen = not fullscreen
    root.attributes("-fullscreen", fullscreen)
    ui_resize()

def end_fullscreen(event=None):
    global root
    global fullscreen

    fullscreen = False
    root.attributes("-fullscreen", False)
    ui_resize()

def ui_resize(event=None):
    global tkframe
    global status_dfont
    global count_dfont
    global quantity_dfont

    new_size = -max(12, int((tkframe.winfo_width() / 12)))
    status_dfont.configure(size=new_size)
    
    new_size = -max(12, int((tkframe.winfo_width() / 6)))
    count_dfont.configure(family=' Sans', weight="bold", size=new_size)

    new_size = -max(12, int((tkframe.winfo_width() / 20)))
    quantity_dfont.configure(size=new_size)

def change_status(current_in):
    global max_label
    global max_amount
    global quantity_label

    normal_color = "#1fc017"
    warning_color = "#d88e2e"

    if max_amount > current_in:
        tkframe.configure(bg=normal_color)
        
        status_label.configure(text="PLEASE ENTER!")
        status_label.configure(bg=normal_color)
        
        count_label.configure(bg=normal_color)
        quantity_label.configure(bg=normal_color)
        max_label.configure(bg=normal_color)
        
        button_quit.configure(bg=normal_color)

    elif max_amount <= current_in:
        tkframe.configure(bg=warning_color)
        
        status_label.configure(text="Please Wait!")
        status_label.configure(bg=warning_color)
        
        count_label.configure(bg=warning_color)
        quantity_label.configure(bg=warning_color)
        max_label.configure(bg=warning_color)
        
        button_quit.configure(bg=warning_color)

    count_text = "{}".format(current_in)
    count_label.configure(text=count_text) 
    
# Remove the bounding boxes with low confidence using non-maxima suppression
def postprocess(frame, outs):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    rects = []
    classIds = []
    confidences = []
    boxes = []
    
    for out in outs:
        for detection in out:
            scores = detection[5:]
            classId = np.argmax(scores)
            confidence = scores[classId]
            
            if confidence > confThreshold:
                center_x = int(detection[0] * frameWidth)
                center_y = int(detection[1] * frameHeight)
                width = int(detection[2] * frameWidth)
                height = int(detection[3] * frameHeight)
                left = int(center_x - width / 2)
                top = int(center_y - height / 2)
                classIds.append(classId)
                confidences.append(float(confidence))
                boxes.append([left, top, width, height])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, confThreshold, nmsThreshold)
    for i in indices:
        box = boxes[i]
        left = box[0]
        top = box[1]
        width = box[2]
        height = box[3]
        
        if classIds[i] == 0:
            rects.append((left, top, left + width, top + height))
            objects = ct.update(rects)
            counting(objects, frame)

def counting(objects, frame):
    global totalDown
    global totalUp
    
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    for (objectID, centroid) in objects.items():
        to = trackableObjects.get(objectID, None)
        
        if to is None:
            to = TrackableObject(objectID, centroid)
        else:
            x = [c[0] for c in to.centroids]
            direction = centroid[0] - np.mean(x)
            to.centroids.append(centroid)
            
            if not to.counted:
                if direction < 0 and centroid[0] in range(frameWidth//2 - 30, frameWidth//2 + 30):
                    totalUp += 1
                    to.counted = True
                elif direction > 0 and centroid[0] in range(frameWidth//2 - 30, frameWidth//2 + 30):
                    totalDown += 1
                    to.counted = True
                    
        trackableObjects[objectID] = to
        cv2.circle(frame, (int(centroid[0]), int(centroid[1])), 4, (0, 255, 0), -1)
        
        draw_str(frame, (20, 40), 'passed people: %d' % totalUp)
        draw_str(frame, (20, 64), 'passed people: %d' % totalDown)
        
    info = [
        ("Up", totalUp),
        ("Down", totalDown),
    ]

    # loop over the info tuples and draw them on our frame
    for (i, (k, v)) in enumerate(info):

        text = "{}".format(v)
        if k == 'Up':
            draw_str(frame, (20, 40), 'passed people: %s' % text)
        if k == 'Down':
            draw_str(frame, (20, 64), 'passed people: %s' % text)
            
def getOutputsNames(net):
    layersNames = net.getLayerNames()
    return [layersNames[i - 1] for i in net.getUnconnectedOutLayers()]

def update():
    global root 
    
def people_counting(args, ev, conn):
    FaceCounter(args, ev, conn).run()
    
class FaceCounter:
    def __init__(self, args, ev, conn):
        
        conn.send("0")

        self.args = args
        self.ev = ev
        self.conn = conn
        
        self.vs = VideoStream(src=0).start()
        self.detector = dlib.get_frontal_face_detector()
        
    def run(self):
        global evt
        global dcount

        while not evt.is_set(): 
            frame = self.vs.read()
            frame = cv2.flip(frame, 1)
            
            winName = 'People Counting System'
            
            blob = cv2.dnn.blobFromImage(frame, 1/255, (inpWidth, inpHeight), [0,0,0], 1, crop=True)
            net.setInput(blob)
            outs = net.forward(getOutputsNames(net))
            postprocess(frame, outs)
            
            cv2.imshow(winName, frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='People Tracking and Counting Project')
    parser.add_argument('--video', help='Path to video file.')
    
    args = parser.parse_args()
    
    # Load names of classes
    classesFile = "coco.names"
    classes = None
    with open(classesFile, 'rt') as f:
        classes = f.read().rstrip('\n').split('\n')
    
    root = tk.Tk()
    root.title("Sentinel")
    
    tkframe = tk.Frame(root, bg="green")
    tkframe.pack(fill=tk.BOTH, expand=1)
    
    status_dfont = tkFont.Font(size=12)
    status_label = tk.Label(tkframe, text="Please Enter!", font=status_dfont, fg="white", bg="green")
    status_label.grid(row=0, column=0, padx=20, pady=20)
    
    count_dfont = tkFont.Font(size=24)
    count_label = tk.Label(tkframe, textvariable=dcount, font=count_dfont, fg="white", bg="green")
    count_label.grid(row=1, column=0, padx=5, pady=5)

    quantity_dfont = tkFont.Font(size=12)
    quantity_label = tk.Label(tkframe, text="Capacity", font=quantity_dfont, fg="white", bg="green")
    quantity_label.grid(row=2, column=0, padx=15, pady=5, sticky=tk.W)

    max_label = tk.Label(tkframe, text="{}".format(max_amount), font=status_dfont, fg="white", bg="green")
    max_label.grid(row=2, column=0, padx=15, pady=5, sticky=tk.E)

    button_dfont = tkFont.Font(size=12)
    button_quit = tk.Button(tkframe,
                            text="Quit",
                            font=button_dfont,
                            command=stop_counting,
                            borderwidth=0,
                            highlightthickness=0,
                            fg='gray10')                            
    button_quit.grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)

    tkframe.rowconfigure(0, weight=2)
    tkframe.rowconfigure(1, weight=4)
    tkframe.columnconfigure(0, weight=1)

    root.bind('<F11>', toggle_fullscreen)
    root.bind('<Escape>', end_fullscreen)
    root.bind('<Configure>', ui_resize)
    
    toggle_fullscreen()
    
    parent_conn, child_conn = Pipe()
    manager = Manager()
    share_count = manager.Value("i", 0)

    process = Process(target=people_counting, args=(args, evt, child_conn))
    process.start()

    root.after(1000, update)
    root.mainloop()
    
 



