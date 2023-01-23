import http.server
import socket
import os
import threading
import time
"""
V1.0 created on 23.12.2022 by  S. Ferreira

This script shows how a request server for the Open_CEM project could look like.
The server gets started with running this script. In the do_GET methode is the code that will be executed if a certain 
request has been made to the server. The request could for example come from a shelly button.
"""


CWD = os.getcwd()
PORT = 8000
DIRECTORY_SERVER = "/Open_CEM/Open_CEM_localServer"

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


print(f"server runs on: {get_ip_address()}:{PORT}")

# Create a request handler class
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY_SERVER, **kwargs)

    # this function handles requests that are made to the server
    def do_GET(self):
        if self.path == "/":
            print("main page visited")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Open_CEM local Server</h1></body></html>")   # html that will be shown in browser

        # button single press
        if self.path == "/1":

            # put here code that gets executed if /1 is requested

            print("one time press")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>1 Pressed</h1></body></html>")   # response that would show in the browser

        # button double press
        if self.path == "/2":
            print("double press")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>2 Pressed</h1></body></html>")

        # button triple press
        if self.path == "/3":
            print("triple press")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>3 Pressed</h1></body></html>")

        # button long press
        if self.path == "/long":
            print("long press")
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Long Pressed</h1></body></html>")

# initialize the server
myServer = http.server.HTTPServer(("", PORT), CustomHandler)

# start a thread in which the server runs
thread1 = threading.Thread(target=myServer.serve_forever)
thread1.start()

# server can be stopped with typing q into the console
while True:
    if input("press q to stop server\n") == "q":
        break

# shut down the server
myServer.shutdown()
thread1.join()
print("sever shutdown")
