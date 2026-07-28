import tkinter as tk
import serial

serialPort = "COM3"
ser = serial.Serial(serialPort)
serBuffer = ""

root = tk.Tk()
# Setting some window properties
root.title("Tk Example")
root.minsize(200, 200)
root.maxsize(500, 500)
root.geometry("300x300+50+50")

def value_changed(event):
    label.config(text=event.widget.get())

scale = tk.Scale(root, from_=0, to=180, orient="horizontal")
scale.bind("<Motion>", value_changed)
scale.pack(padx=5, pady=5, fill="x")

# A helper label to show the selected value
label = tk.Label(root, text="0")
label.pack(padx=5, pady=5, fill="x")

# make a text box to put the serial output
log = tk.Text ( root, width=30, height=30, takefocus=0)
log.pack()

def readSerial():
    while True:
        c = ser.read() # attempt to read a character from Serial
        
        #was anything read?
        if len(c) == 0:
            break
        
        # get the buffer from outside of this function
        global serBuffer
        
        # check if character is a delimeter
        if c == '\r':
            c = '' # don't want returns. chuck it
            
        if c == '\n':
            serBuffer += "\n" # add the newline to the buffer
            
            #add the line to the TOP of the log
            log.insert('0.0', serBuffer)
            serBuffer = "" # empty the buffer
        else:
            serBuffer += c # add to the buffer
    
    root.after(10, readSerial) # check serial again soon

# after initializing serial, an arduino may need a bit of time to reset
root.after(100, readSerial)

root.mainloop()
