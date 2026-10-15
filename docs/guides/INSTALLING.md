# Installation

## Raspberry Pi OS

The reference setup is a Raspberry Pi 3 Model B+ with Raspberry Pi OS 64-bit and an 800×480 DSI touchscreen. Other Raspberry Pi models and landscape displays can work too. Screenshots of first-run setup and hourly details are in the project [README](../../README.md#screenshots).

### Install and run

1. Install Raspberry Pi OS with the desktop environment, connect the touchscreen, and connect the Pi to the internet. A desktop session is needed for Chromium kiosk mode.
2. Open a terminal on the Pi and install Git, Python 3, and Chromium if they are not already present:

   ```sh
   sudo apt update
   sudo apt install git python3 chromium
   ```

   On an older Raspberry Pi OS image, the browser package may instead be named `chromium-browser`.
3. Download the project and enter its directory:

   ```sh
   git clone https://github.com/mderdouri/Dayglance.git
   cd Dayglance
   ```

4. Start the local app server:

   ```sh
   python3 server.py
   ```

   Leave this terminal open while using Dayglance. By default, the server listens only on the Pi itself at `127.0.0.1:8080`.
5. In Chromium on the Pi, open [http://localhost:8080](http://localhost:8080). On first launch, search for your city or ZIP/postal code, choose the matching suggestion, and allow the forecast to load.
6. For a full-screen touchscreen display, open a second terminal and start Chromium in kiosk mode:

   ```sh
   chromium --kiosk --noerrdialogs --disable-infobars http://localhost:8080
   ```

   If the executable is named `chromium-browser` on your image, use that command instead. To exit kiosk mode, connect a keyboard and press `Alt+F4`.
7. To stop the server, return to its terminal and press `Ctrl+C`.

### Optional desktop auto-start

1. In the project directory on the Pi, install the desktop login entry once:

   ```sh
   sh install-autostart.sh
   ```

2. Open Dayglance at `http://localhost:8080`, tap the gear button, and turn on **Start Dayglance when the desktop logs in**. You can also choose whether the browser starts in kiosk mode.
3. Log out and back in to apply the startup options. They are stored in the Pi-local `device-settings.json`; the settings screen saves them without restarting the forecast server. They apply when the Dayglance launcher next runs. The startup script does nothing while auto-start is turned off.

To configure the display without using its touchscreen, edit or copy `config.json` into the project directory before starting the app. It supports locations, units, clock format, refresh interval, hourly-view return timer, optional hourly navigation buttons, and startup defaults. See [CONFIGURATION.md](CONFIGURATION.md) for the complete schema and allowed values. Browser settings changed through the UI are saved in that browser and override the JSON preference defaults; Pi startup changes made through the UI are saved in `device-settings.json` and override the JSON startup defaults. Swipe or drag the hourly forecast cards to scroll through the day. Location edits and removals made in the UI are saved per browser; hiding a `config.json` location affects only that device.

To open Dayglance from another device on the same trusted local network, start the server with `python3 server.py --host 0.0.0.0 --port 8080`, then browse to `http://<pi-address>:8080`. Do not expose the simple development server directly to the public internet.

To launch the display automatically after login, configure the desktop session to start the server before Chromium. Keep the system's screensaver and power settings under the operating system's control; Dayglance does not request a wake lock.

The app is a static browser client. Forecast and location searches require internet access. The cached app shell can help the UI start without a connection, while fresh forecast data may be unavailable.

## Other computers

Install Python 3, clone the repository, and run `python3 server.py`. Visit `http://localhost:8080` in a current browser.

## Server options

```sh
python3 server.py --help
python3 server.py --host 127.0.0.1 --port 8080
```

The default binds to loopback (`127.0.0.1`). Use `--host 0.0.0.0` only when you need access from another device on your trusted local network. Do not expose this simple development server directly to the public internet.
