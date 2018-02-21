import sys, getopt

#sys.path.append('.')
import RTIMU
import os
import time
import math
import numpy as np
from finangler import FinAngler
from threading import Thread, Lock

############################# IMU SETUP #############################
SETTINGS_FILE = "RTIMULib"

print("Using settings file " + SETTINGS_FILE + ".ini")
if not os.path.exists(SETTINGS_FILE + ".ini"):
  print("Settings file does not exist, will be created")

s = RTIMU.Settings(SETTINGS_FILE)
imu = RTIMU.RTIMU(s)

print("IMU Name: " + imu.IMUName())

if (not imu.IMUInit()):
    print("IMU Init Failed")
    sys.exit(1)
else:
    print("IMU Init Succeeded")

# this is a good time to set any fusion parameters
imu.setSlerpPower(0.02)
imu.setGyroEnable(True)
imu.setAccelEnable(True)
imu.setCompassEnable(True)

poll_interval = imu.IMUGetPollInterval()
print("Recommended Poll Interval: %dmS\n" % poll_interval)


def radians_to_us(theta):
    us = theta/np.pi*500 + 1500
    return max(1000, min(2000, us))


############################ SERVO THREAD #############################
# Shared memory angle values for servos
_angles             = [0, 0, 0]  # start straight up
_angles_thread_lock = Lock()

def write_to_servos():
    _angles_thread_lock.acquire()
    most_recent_angles = _angles
    _angles_thread_lock.release()
    for angle in most_recent_angles:
        os.system("echo {}={}us > /dev/servoblaster".format(radians_to_us(angle)))
    time.sleep(0.05)  # 20 Hz update rate, once per 50 ms  # TODO optimize this
    
servo_thread = Thread(target=write_to_servos)
servo_thread.start()
print("Started ServoBlaster thread.")



############################# SERVO SETUP #############################
os.system('sudo servod --p1pins="11,13,15"')
fa = FinAngler()
fa.velocity = 1.
first_yaw = None

tic=0
counter = 0
fusionPose = None
while True:
    if imu.IMURead():
        data = imu.getIMUData()
        fusionPose = data["fusionPose"]
        counter += 1
        #print("r: %f p: %f y: %f" % (math.degrees(fusionPose[0]), 
        #    math.degrees(fusionPose[1]), math.degrees(fusionPose[2])))
        if first_yaw is None:
            first_yaw = fusionPose[2]
        #elif counter > 6:
        #    counter = 0

    elif fusionPose is not None:
        print(time.time()-tic, fusionPose)
        tic = time.time()
        push_angle = np.arctan2(np.sin(fusionPose[1]), np.sin(fusionPose[0]))  
        push_force = np.arccos(np.cos(fusionPose[1])*np.cos(fusionPose[0]))/10.
        computed_angles = fa.calc_angles(
            push_angle, push_force, (fusionPose[2]-first_yaw) / 10.)

        #angles = fa.calc_angles(0,0,(fusionPose[2] - first_yaw)/10.)
        #print time.time() - tic, math.degrees(fusionPose[2] - first_yaw), angles

        # Update shared memory angles to newly computed ones
        _angles_thread_lock.acquire()
        _angles = computed_angles
        _angles_thread_lock.release()


        # for index, angle in enumerate(angles):
        #     os.system("echo {}={}us > /dev/servoblaster".format(index,radians_to_us(angle)))

        # time.sleep(.1)
        #time.sleep(poll_interval*1./1000.0)

