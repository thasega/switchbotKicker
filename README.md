# switchbotKicker
A high-accuracy scheduling agent written in MicroPython for triggering SwitchBot scenes at precise times.

## Required Packages
- aiohttp  
- microdot
  
## Operating Environment
Tested and confirmed to work on Raspberry Pi Pico W.  
MicroPython firmware used is [RPI_PICO_W-20241129-v1.24.1.uf2](https://micropython.org/download/RPI_PICO_W/)

## Motivation
SwitchBot's standard **Automation** has low accuracy in executing scenes at the scheduled time,  
and sometimes the execution fails entirely. Due to personal reasons, I need the scenes to be executed with a few seconds of accuracy.  
However, I didn't want to set up large and complex equipment just for that.  

## Installation Steps
1. **Buy a Raspberry Pi Pico W** :)
   - Make sure to note down its **MAC address** using any method.

2. **Install MicroPython firmware**  
   - Flash the **MicroPython firmware** onto the Pico W and set it up to run MicroPython.

3. **Install required packages**  
   - Use a package manager (**I used Thonny**) to install aiohttp and microdot packages into Pico W.

4. **Modify `usersettings.py`**  
   - Edit the `usersettings.py` file from this repository to fit your environment.  
   - This includes:  
     - **WiFi SSID and password**  
     - **SwitchBot API token**  
   - The file also contains **text resources for the user interface**.  
     - Feel free to change them to your preferred language.  
     - Since I’m Japanese, I like it as it is :)  

5. **Copy files to the Pico W**  
   - Transfer the modified `usersettings.py` and `main.py` from this repository to the Pico W.

6. **Run the device**  
   - Disconnect the **Pico W** from your PC and power it separately.  
   - The **LED on the Pico W will turn on**.  
   - If `usersettings.py` is set up correctly and the device **connects to WiFi**, the LED **will turn off**.

### Finding the Web Interface
- Once the LED turns off, the **Pico W's web service is running**.  
- Use the **MAC address** from Step 1 to find the Pico W’s **IP address** :)
- Open the IP address in a **web browser**, and the **control interface** should appear. 

## Effect
The scenes are now executed with an accuracy of about **1 second** from the scheduled time.  
I’m very satisfied with the result! :)
