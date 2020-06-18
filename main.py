#used libraries:
# - requests
# - selenium: webdriver-manager

import requests

from selenium import webdriver
import RPi.GPIO as GPIO
import time
from time import sleep
import threading

#TODO read this from a file.
KEY = "0001"

#The button is on GPIO pin 11
button = 11

#Set up the GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def main():
        print("RemoteAD v1.0")
        print(timeFormat() + "Setting up Chrome driver...")

        global STATE
        STATE = "INIT"

        #Set the options for Chrome
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        chrome_options.add_argument("--start-maximized")

        #Set the driver to Chrome, apply the options, set the window to full screen, and go to a specified page.
        global driver
        driver = webdriver.Chrome(options=chrome_options)
       # driver.fullscreen_window()
        driver.get("about:blank")

        print(timeFormat() + "Signing in with server...")
        signIn()

#We need to sign in to the server before it will accept our requests
def signIn():

        #The Endpoint, where we sign in
        ENDPOINT = "https://api.thedutchmc.nl/remotead/signin"

        #We provide our key in the data, as a String
        data = {
                'KEY':KEY
        }

        #Make the request
        request = requests.post(url = ENDPOINT, data = data, timeout = 5);

        #We want the status code, if the login was successful this wil be 200, if not it will be a 401
        reply = request.status_code

        #200 -- OK; Start the GPIO Listener
        if(reply == 200):
                print(timeFormat() + "Client authorized by server.")
                gpioListener()

        #401 -- UNAUTHORIZED; Our key is invalid
        elif(reply == 401):
                print(timeFormat() + "Client is not authorized by server.")

        #Anything else, e.g a timeout, we just start over again
        else:
                signIn()



#Listens to the state of the GPIO pin (Ie the button), and acts accordingly
def gpioListener():
        global STATE

        shouldListen = True
        while shouldListen:

                #If the GPIO is high, wait until it is high for 1 second, then send a video request
                if GPIO.input(button) == GPIO.HIGH:
                        sleep(1)
                        if GPIO.input(button) == GPIO.HIGH and STATE != "PLAYING":
                                shoudListen = False
                                requestVideo()

                #If the GPIO is low, wait until it has been low for 2 seconds, then open an image, and start the GPIO listener again
                elif GPIO.input(button) == GPIO.LOW:
                        sleep(2)
                        if GPIO.input(button) == GPIO.LOW and STATE != "HOLD":
                                shoudListen = False
                                stopVideoPlay()
                                gpioListener()

#Here we send a request to the server for video keys
def requestVideo():

        if GPIO.input(button) == GPIO.LOW:
                return

        print(timeFormat() + "Requesting next batch of videos from server")

        #This is our endpoint, ie where we get the keys from
        ENDPOINT = "https://api.thedutchmc.nl/remotead/videorequest"

        #The server expects us to send our client key along, so we put this in the data.
        data = {
                'KEY':KEY
        }
        #Make the request
        request = requests.post(url = ENDPOINT, data = data)

        # Message Format: [Array]
        # Client Key
        # video key : video length in seconds
        keysWithLength = request.text.split(",")

        keysDictionary = {}

        #Loop over the keysWithLength array, if the element is not emoty, split it on :, and put it into the dictionary
        for keyWithLength in keysWithLength:
                if keyWithLength is not '':
                        elements = keyWithLength.split(":")
                        keysDictionary[elements[0]] = elements[1]

        #Turn the dictionary into two seperate lists
        global keyList
        keyList = list(keysDictionary.keys())
        global lengthList
        lengthList = list(keysDictionary.values())
        global videoIndex
        videoIndex = 1

        #Start the video player thread
        videoThread = threading.Thread(target = videoPlayerThread, args = (keyList[0], lengthList[0]))
        videoThread.start()

#Thread to play the video
def videoPlayerThread(key, length):
        #Set the client state to "PLAYING"
        global STATE
        STATE = "PLAYING"

        #Create the URL we're playing
        url = "https://www.youtube.com/embed/" + key + "?&autoplay=1&showinfo=0&modestbranding=0&controls=0&disablekb=1&vq=hd720&rel=0"
        driver.get(url)

        #Sleep for the length of the video we're playing
        sleep(int(length))

        #Video has finished playing
        #This is our endpoint, ie where we get the keys from
        ENDPOINT = "https://api.thedutchmc.nl/remotead/videocounter"

        #The server expects us to send our client key along, so we put this in the data.
        data = {
                'KEY':KEY,
                'videoKey':key
        }
        #Make the request
        if GPIO.input(button) == GPIO.HIGH:
                request = requests.post(url = ENDPOINT, data = data)

        #If the video index +1 is less than the size of keyList, and the button is still high, play the next video.
        if videoIndex + 1 <= len(keyList) and GPIO.input(button) == GPIO.HIGH:
                playNextVideo()
        elif GPIO.input(button) == GPIO.LOW:
                requestVideo()
        else:
                stopVideoPlay()

def playNextVideo():
        global videoIndex

        videoThread = threading.Thread(target = videoPlayerThread, args = (keyList[videoIndex], lengthList[videoIndex]))
        videoThread.start()
        videoIndex += 1

#Load the image that is to be displayed when the sensor no longer triggers
def stopVideoPlay():
        global STATE
        STATE = "HOLD"
        url = "about:blank"
        driver.get(url);

def timeFormat():
        return "[" + time.strftime("%H:%M:%S", time.localtime()) + "] "

main()