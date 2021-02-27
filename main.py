#!/usr/bin/env python3
#
# Python user-space driver for ancient Fujifilm FinePix cameras
#
# Based on https://github.com/torvalds/linux/blob/master/drivers/media/usb/gspca/finepix.c
#
# (C)2021 Jannik Vogel
#
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the "Software"),
#  to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense,
#  and/or sell copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.

import time
import io
import sys

import usb1
from PIL import Image
import pyvirtualcam
import numpy as np


# List of cameras: (VID, PID)
supported_devices = [
    (0x04cb, 0x0104),
    (0x04cb, 0x0109),
    (0x04cb, 0x010b),
    (0x04cb, 0x010f),
    (0x04cb, 0x0111),
    (0x04cb, 0x0113),
    (0x04cb, 0x0115),
    (0x04cb, 0x0117),
    (0x04cb, 0x0119),
    (0x04cb, 0x011b),
    (0x04cb, 0x011d),
    (0x04cb, 0x0121),
    (0x04cb, 0x0123),
    (0x04cb, 0x0125),
    (0x04cb, 0x0127),
    (0x04cb, 0x0129),
    (0x04cb, 0x012b),
    (0x04cb, 0x012d),
    (0x04cb, 0x012f),
    (0x04cb, 0x0131),
    (0x04cb, 0x013b),
    (0x04cb, 0x013d),
    (0x04cb, 0x013f)
]

INTERFACE = 0
ENDPOINT = 1


# Supported commands
reset_cmd  = bytes([0xc6, 0, 0, 0, 0, 0, 0,    0, 0x20, 0, 0, 0]) # reset
fr_req_cmd = bytes([0xd3, 0, 0, 0, 0, 0, 0, 0x01,    0, 0, 0, 0]) # fr req

FPIX_TIMEOUT = 250
FPIX_MAX_TRANSFER = 0x2000

NEXT_FRAME_DELAY = 35


# Create a USB context
context = usb1.USBContext()
if context is None:
  print("Unable to create USB context")
  sys.exit(1)

# Attempt to find a camera
cameras = []
device_list = context.getDeviceList(skip_on_error=True)
for device in device_list:

  # Check if this device is supported by us
  for supported_device in supported_devices:
    vid, pid = supported_device
    if vid != device.getVendorID():
      continue
    if pid != device.getProductID():
      continue

    # Add device to list of cameras
    cameras += [device]

# Check if we found any device
if len(cameras) == 0:
    print("Unable to find a supported device")
    sys.exit(1)

# Open the first camera that we found
handle = cameras[0].open()
if handle is None:
    print("Unable to open device")
    sys.exit(1)

# Open the USB interface on the physical camera
with handle.claimInterface(INTERFACE):


    # Helper function to send a command to the physical camera
    def command(data):
      request_type = usb1.REQUEST_TYPE_CLASS | usb1.RECIPIENT_INTERFACE
      request = usb1.REQUEST_GET_STATUS
      value = 0
      index = 0
      handle.controlWrite(request_type, request, value, index, data, timeout=FPIX_TIMEOUT)

    # Helper function to read a single frame via USB
    def readFrame():
      command(fr_req_cmd)
      frame = b""
      while True:
        data = handle.bulkRead(ENDPOINT, FPIX_MAX_TRANSFER,timeout=FPIX_TIMEOUT)
        frame += data
        if (len(data) < FPIX_MAX_TRANSFER) or ((data[-2] == 0xFF) and (data[-1] == 0xD9)):
          break
      return frame


    # Create a virtual camera
    virtual_camera = pyvirtualcam.Camera(width=320, height=240, fps=30)
    if virtual_camera is None:
      print("Unable to create virtual camera")
      sys.exit(1)

    # Reset the camera and reset our framecounter
    command(reset_cmd)
    frameIndex = 0

    # Loop to process frames
    while True:

      # Read frame from physical camera
      frame = readFrame()

      # Dump frame to disk
      if False:
        open("frame_%d.jpg" % frameIndex, "wb").write(frame)
        frameIndex += 1

      # Decode the JPEG to a plain RGBA image
      image = Image.open(io.BytesIO(frame))
      image = image.convert('RGBA')

      # Send frame to virtual camera
      pixels = np.asarray(image)
      virtual_camera.send(pixels)

      # Wait for next frame
      #FIXME: We should subtract the time we wasted in the USB and virtual-camera code
      if False:
        virtual_camera.sleep_until_next_frame()
      else:
        time.sleep(NEXT_FRAME_DELAY / 1000.0)
