#!/usr/bin/env python3

import cv2
import time
import sys

def benchmark(num_times):
    """
    call face_cascade.detectMultiScale 'num_times' number of times 
    and return the execution time
    """
    start = time.clock_gettime(time.CLOCK_REALTIME)
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

    img = cv2.imread('test.jpg')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    overhead_time = time.clock_gettime(time.CLOCK_REALTIME) - start
    start = time.clock_gettime(time.CLOCK_REALTIME)
    
    for i in range(0,num_times): 
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    face_detect_time = time.clock_gettime(time.CLOCK_REALTIME) - start

    return (overhead_time,face_detect_time)

if __name__ == '__main__':
    import sys

    num_times = int(sys.argv[1])
    (overhead_time,face_detect_time) = benchmark(num_times)
    print("overhead_time to load classifier and image -> %f seconds" % overhead_time)
    print("time to do %d face detections -> %f seconds" % (num_times,face_detect_time)) 
 



